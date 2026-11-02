"""Indexers for SEG-D records and multi-file catalogs."""

from __future__ import annotations

import logging
from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any

import numpy as np
from fsspec.utils import merge_offset_ranges

from segd.arrays import HeaderArray
from segd.arrays import TraceArray
from segd.transforms import TransformPipeline

if TYPE_CHECKING:
    from pathlib import Path

    from fsspec import AbstractFileSystem
    from numpy.typing import NDArray

    from segd.catalog import RecordCatalog
    from segd.schema import TraceSpec
    from segd.schema.base import BaseDataType

    IntDType = np.signedinteger[Any]


logger = logging.getLogger(__name__)


def merge_cat_file(
    fs: AbstractFileSystem,
    url: str | Path,
    starts: list[int],
    ends: list[int],
    block_size: int = 8_388_608,
) -> bytearray:
    """Merge sequential byte start/ends and fetch from store."""
    paths = [url] * len(starts)

    paths, starts, ends = merge_offset_ranges(
        paths,
        starts,
        ends,
        max_block=block_size,
        sort=True,
    )

    buffer_bytes = fs.cat_ranges(
        paths=paths,
        starts=starts,
        ends=ends,
    )

    return bytearray(b"".join(buffer_bytes))


def bounds_check(indices: NDArray[IntDType], max_: int, type_: str) -> None:
    """Check if indices are out of bounds (negative, or more than max)."""
    oob_indices = np.where((indices < 0) | (indices >= max_))[0]

    if len(oob_indices) > 0:
        msg = (
            f"Requested {type_} indices {oob_indices} are out of bounds. SEG-D "
            f"catalog has {max_} traces. Valid indices are "
            f"[0, {max_ - 1})."
        )
        raise IndexError(msg)


def _handle_raw_dtype(dtype: np.dtype[Any], raw: bool) -> np.dtype[Any]:
    """Handle casting a proper dtype to its void version if requested."""
    return np.dtype((np.void, dtype.itemsize)) if raw else dtype


class AbstractIndexer(ABC):
    """Abstract class for indexing and fetching structured data."""

    kind: str = "Abstract"

    def __init__(
        self,
        catalog: RecordCatalog,
        spec: BaseDataType,
        transform_pipeline: TransformPipeline | None = None,
    ):
        self.catalog = catalog
        self.spec = spec
        self.max_value = catalog.num_traces
        self.transform_pipeline = (
            TransformPipeline() if transform_pipeline is None else transform_pipeline
        )

    @abstractmethod
    def indices_to_fetches(
        self, indices: NDArray[IntDType]
    ) -> list[tuple[AbstractFileSystem, str, int, int]]:
        """Return list of (fs, url, start, end) byte ranges for indices."""

    @abstractmethod
    def decode(self, buffer: bytearray, raw: bool) -> NDArray[Any]:
        """How to decode the bytes after reading."""

    def post_process(self, data: NDArray[Any]) -> NDArray[Any]:
        """Apply transforms to the data after decoding."""
        return self.transform_pipeline.apply(data)

    def normalize_and_validate_query(
        self, item: int | list[int] | NDArray[IntDType] | slice
    ) -> NDArray[IntDType]:
        """Operator for integers, lists, and slices with bounds checking."""
        if isinstance(item, slice):
            if item.step == 0:
                msg = "Step of 0 is invalid for slicing."
                raise ValueError(msg)

            start = item.start or 0
            stop = item.stop or self.max_value
            start_stop = np.asarray([start, stop - 1])

            bounds_check(start_stop, self.max_value, self.kind)
            indices = np.arange(*item.indices(self.max_value))

        else:
            indices = np.atleast_1d(item)
            bounds_check(indices, self.max_value, self.kind)

        if len(indices) == 0:
            msg = "Couldn't parse request. Please ensure it is a valid index."
            raise IndexError(msg)

        return indices

    def __getitem__(self, item: int | list[int] | NDArray[IntDType] | slice) -> Any:  # noqa: ANN401
        """Operator for integers, lists, and slices with bounds checking."""
        indices = self.normalize_and_validate_query(item)
        data = self.fetch(indices)
        return self.post_process(data)

    def fetch(self, indices: NDArray[IntDType], raw: bool = False) -> NDArray[Any]:
        """Fetches and decodes binary data from the given indices."""
        unique_indices, index_order, counts = np.unique(
            indices,
            return_inverse=True,
            return_counts=True,
        )

        if len(indices) != len(unique_indices):
            duplicate_mask = counts > 1
            values = unique_indices[duplicate_mask]
            counts = counts[duplicate_mask]
            duplicates = {int(v): int(c) for v, c in zip(values, counts, strict=True)}
            logger.warning("Duplicate indices requested with counts %s:", duplicates)

        fetches = self.indices_to_fetches(unique_indices)

        # Group by (fs id, url) for merge_cat_file
        grouped: dict[str, tuple[AbstractFileSystem, list[int], list[int]]] = {}
        order_map: list[tuple[str, int]] = []
        for fs, url, start, end in fetches:
            key = url
            if key not in grouped:
                grouped[key] = (fs, [], [])
            grouped[key][1].append(start)
            grouped[key][2].append(end)
            order_map.append((key, len(grouped[key][1]) - 1))

        chunks: dict[str, bytearray] = {}
        for key, (fs, starts, ends) in grouped.items():
            chunks[key] = merge_cat_file(fs, key, starts, ends)

        # Reassemble in unique_indices order. merge_cat_file sorts ranges, so decode
        # per-request by reading individual ranges when multiple files / non-contig.
        # Simpler path: fetch each unique index independently when multi-file.
        if len(grouped) == 1 and len(unique_indices) == len(fetches):
            only_key = next(iter(chunks))
            array = self.decode(chunks[only_key], raw)
            return array[index_order].squeeze()

        # General path: per-index fetch to preserve mapping across files.
        pieces: list[NDArray[Any]] = []
        for fs, url, start, end in fetches:
            buf = bytearray(fs.read_block(url, offset=start, length=end - start))
            pieces.append(self.decode(buf, raw))
        array = np.concatenate(pieces)
        return array[index_order].squeeze()


def _trace_byte_range(
    catalog: RecordCatalog,
    index: int,
    *,
    header_only: bool = False,
    data_only: bool = False,
) -> tuple[AbstractFileSystem, str, int, int]:
    """Compute byte range for one global trace index."""
    record, local = catalog.locate(int(index))
    th = record.info.trace_header_size
    samples = record.info.samples * 4
    start = record.local_offset(local)
    if header_only:
        return record.fs, record.url, start, start + th
    if data_only:
        return record.fs, record.url, start + th, start + th + samples
    return record.fs, record.url, start, start + th + samples


class TraceIndexer(AbstractIndexer):
    """Indexer for reading traces (headers + data)."""

    spec: TraceSpec
    kind: str = "trace"

    def indices_to_fetches(
        self, indices: NDArray[IntDType]
    ) -> list[tuple[AbstractFileSystem, str, int, int]]:
        """Convert trace indices to byte ranges."""
        return [_trace_byte_range(self.catalog, int(i)) for i in indices]

    def decode(self, buffer: bytearray, raw: bool = False) -> TraceArray:
        """Decode whole traces (header + data)."""
        dtype = _handle_raw_dtype(self.spec.dtype, raw)
        data = np.frombuffer(buffer, dtype=dtype)
        return TraceArray(data)


class HeaderIndexer(AbstractIndexer):
    """Indexer for reading physical trace headers only."""

    spec: TraceSpec
    kind: str = "header"

    def indices_to_fetches(
        self, indices: NDArray[IntDType]
    ) -> list[tuple[AbstractFileSystem, str, int, int]]:
        """Convert header indices to byte ranges (without trace data)."""
        return [
            _trace_byte_range(self.catalog, int(i), header_only=True) for i in indices
        ]

    def decode(self, buffer: bytearray, raw: bool = False) -> HeaderArray:
        """Decode physical headers only."""
        dtype = _handle_raw_dtype(self.spec.dtype["header"], raw)
        data = np.frombuffer(buffer, dtype=dtype)
        return HeaderArray(data)


class DataIndexer(AbstractIndexer):
    """Indexer for reading trace data samples only."""

    spec: TraceSpec
    kind: str = "data"

    def indices_to_fetches(
        self, indices: NDArray[IntDType]
    ) -> list[tuple[AbstractFileSystem, str, int, int]]:
        """Convert data indices to byte ranges (without trace headers)."""
        return [
            _trace_byte_range(self.catalog, int(i), data_only=True) for i in indices
        ]

    def decode(self, buffer: bytearray, raw: bool = False) -> NDArray[Any]:
        """Decode trace samples only."""
        dtype = _handle_raw_dtype(self.spec.dtype["data"], raw)
        return np.frombuffer(buffer, dtype=dtype)
