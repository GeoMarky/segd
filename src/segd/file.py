"""SEG-D file / multi-record catalog reader."""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING
from typing import Any

import numpy as np

from segd.accessors import TraceAccessor
from segd.arrays import HeaderArray
from segd.catalog import RecordCatalog
from segd.catalog import build_catalog
from segd.config import SegdFileSettings
from segd.config import SegdHeaderOverrides
from segd.indexing import DataIndexer
from segd.indexing import bounds_check
from segd.inference import standard_from_format
from segd.p190 import P190File
from segd.standards import get_segd_standard

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fsspec import AbstractFileSystem
    from numpy.typing import NDArray

    from segd.schema import SegdSpec

    IntDType = np.signedinteger[Any]

logger = logging.getLogger(__name__)


class _LogicalHeaderIndexer:
    """Indexer that returns logical MDIO-compatible headers."""

    kind = "header"

    def __init__(self, segd_file: SegdFile) -> None:
        self._file = segd_file
        self.max_value = segd_file.num_traces

    def normalize_and_validate_query(
        self, item: int | list[int] | NDArray[IntDType] | slice
    ) -> NDArray[IntDType]:
        """Normalize query indices."""
        if isinstance(item, slice):
            if item.step == 0:
                msg = "Step of 0 is invalid for slicing."
                raise ValueError(msg)
            start = item.start or 0
            stop = item.stop or self.max_value
            bounds_check(np.asarray([start, stop - 1]), self.max_value, self.kind)
            return np.arange(*item.indices(self.max_value))
        indices = np.atleast_1d(item)
        bounds_check(indices, self.max_value, self.kind)
        return indices

    def __getitem__(
        self, item: int | list[int] | NDArray[IntDType] | slice
    ) -> HeaderArray:
        """Fetch logical headers."""
        indices = self.normalize_and_validate_query(item)
        result = self._file.accessors.build_logical_headers(
            indices,
            self._file.catalog,
            self._file.navigation,
        )
        squeezed = result.squeeze()
        return HeaderArray(np.asarray(squeezed))


class _LogicalTraceIndexer:
    """Indexer that returns logical traces (header + samples)."""

    kind = "trace"

    def __init__(self, segd_file: SegdFile) -> None:
        self._file = segd_file
        self.max_value = segd_file.num_traces

    def normalize_and_validate_query(
        self, item: int | list[int] | NDArray[IntDType] | slice
    ) -> NDArray[IntDType]:
        """Normalize query indices."""
        if isinstance(item, slice):
            if item.step == 0:
                msg = "Step of 0 is invalid for slicing."
                raise ValueError(msg)
            start = item.start or 0
            stop = item.stop or self.max_value
            bounds_check(np.asarray([start, stop - 1]), self.max_value, self.kind)
            return np.arange(*item.indices(self.max_value))
        indices = np.atleast_1d(item)
        bounds_check(indices, self.max_value, self.kind)
        return indices

    def fetch(self, indices: NDArray[IntDType], raw: bool = False) -> Any:  # noqa: ANN401
        """Fetch traces; raw=True returns physical void records."""
        indices = np.atleast_1d(indices)
        if raw:
            return self._fetch_raw(indices)
        samples = self._file.sample.fetch(indices)
        if samples.ndim == 1:
            samples = samples.reshape(1, -1)
        return self._file.accessors.build_traces(
            indices,
            samples,
            self._file.catalog,
            self._file.navigation,
        )

    def _fetch_raw(self, indices: NDArray[IntDType]) -> NDArray[Any]:
        """Fetch physical demux traces as void dtype of full stride."""
        from segd.indexing import _trace_byte_range  # noqa: PLC0415

        pieces: list[NDArray[Any]] = []
        itemsize = self._file.spec.trace.dtype.itemsize
        void_dtype = np.dtype((np.void, itemsize))
        for index in indices:
            fs, url, start, end = _trace_byte_range(self._file.catalog, int(index))
            buf = fs.read_block(url, offset=start, length=end - start)
            # Physical size may differ from logical dtype itemsize; use physical.
            physical = end - start
            pieces.append(np.frombuffer(buf, dtype=np.dtype((np.void, physical))))
        if not pieces:
            return np.zeros(0, dtype=void_dtype)
        return np.concatenate(pieces)

    def __getitem__(self, item: int | list[int] | NDArray[IntDType] | slice) -> Any:  # noqa: ANN401
        """Fetch logical traces."""
        indices = self.normalize_and_validate_query(item)
        return self.fetch(indices).squeeze()


class SegdFile:
    """Open one or more demultiplexed SEG-D RAW records as a logical file.

    Args:
        url: A single RAW URL or an ordered sequence of RAW URLs.
        spec: Optional SEG-D spec. Inferred from the first record when omitted.
        settings: File settings (endianness, storage options, record order).
        header_overrides: Optional fixed header values applied on read.
        navigation: Optional P190 URL joined onto logical trace headers.
    """

    def __init__(  # noqa: PLR0913
        self,
        url: str | Sequence[str],
        spec: SegdSpec | None = None,
        settings: SegdFileSettings | None = None,
        header_overrides: SegdHeaderOverrides | None = None,
        navigation: str | None = None,
        *,
        cable: int = 1,
        gun: int = 1,
        sail_line_map: dict[str, int] | None = None,
    ) -> None:
        self.settings = settings or SegdFileSettings()
        self.header_overrides = header_overrides or SegdHeaderOverrides()
        self.cable = cable
        self.gun = gun
        self.sail_line_map = sail_line_map

        self.catalog: RecordCatalog = build_catalog(
            url,
            storage_options=self.settings.storage_options,
            order=self.settings.order,
        )
        self.urls = self.catalog.urls
        self.url = self.urls[0]
        self.fs: AbstractFileSystem = self.catalog.records[0].fs

        first = self.catalog.records[0].info
        if spec is None:
            standard = standard_from_format(first.format_code)
            self.spec = get_segd_standard(standard)
        else:
            self.spec = spec.model_copy(deep=True)

        self._update_spec_from_record(first)

        self.navigation: P190File | None = None
        if navigation is not None:
            self.navigation = P190File(
                navigation,
                settings={"storage_options": self.settings.storage_options},
            )

        sail_map = sail_line_map
        if sail_map is None and self.navigation is not None:
            from segd.accessors import build_sail_line_map  # noqa: PLC0415

            sail_map = build_sail_line_map(
                [g.line_name for g in self.navigation.shot_gathers]
            )

        self.accessors = TraceAccessor(
            self.spec.trace,
            self.header_overrides,
            cable=cable,
            gun=gun,
            sail_line_map=sail_map,
        )

        self._sample_indexer = DataIndexer(
            catalog=self.catalog,
            spec=self.spec.trace,
        )
        # Ensure sample dtype uses file endianness
        self.spec.trace.data.samples = first.samples
        self.spec.trace.data.interval = first.sample_interval_us

    def _update_spec_from_record(self, info: Any) -> None:  # noqa: ANN401
        """Fill sample geometry and sizes from a parsed record."""
        self.spec.file_header_size = info.file_header_size
        self.spec.channels_per_record = info.channels
        self.spec.trace.header.item_size = info.trace_header_size
        self.spec.trace.data.samples = info.samples
        self.spec.trace.data.interval = info.sample_interval_us
        self.spec.trace.count = self.catalog.num_traces
        self.spec.trace.offset = info.file_header_size
        self.spec.text_header = info.external_header_text

        if self.settings.endianness is not None:
            self.spec.endianness = self.settings.endianness

    @property
    def num_traces(self) -> int:
        """Total traces across all RAW records."""
        return self.catalog.num_traces

    @property
    def num_records(self) -> int:
        """Number of RAW records."""
        return self.catalog.num_records

    @property
    def samples_per_trace(self) -> int:
        """Samples per trace."""
        samples = self.spec.trace.data.samples
        if samples is None:
            msg = "Samples per trace unknown."
            raise ValueError(msg)
        return samples

    @property
    def sample_interval(self) -> int:
        """Sample interval in microseconds."""
        interval = self.spec.trace.data.interval
        if interval is None:
            msg = "Sample interval unknown."
            raise ValueError(msg)
        return interval

    @property
    def sample_labels(self) -> NDArray[np.int32]:
        """Sample axis labels in microseconds."""
        return np.arange(self.samples_per_trace, dtype=np.int32) * self.sample_interval

    @property
    def file_size(self) -> int:
        """Total size of all RAW files in bytes."""
        return sum(record.file_size for record in self.catalog.records)

    @property
    def text_header(self) -> str:
        """External header text / summary from the first record."""
        return self.spec.text_header or ""

    @cached_property
    def binary_header(self) -> HeaderArray:
        """Logical binary header synthesized from the first record."""
        info = self.catalog.records[0].info
        dtype = self.spec.binary_header.dtype
        header = np.zeros(1, dtype=dtype)
        header["sample_interval"] = info.sample_interval_us
        header["samples_per_trace"] = info.samples
        header["measurement_system_code"] = 1
        header["format_code"] = info.format_code
        header["channels_per_record"] = info.channels
        header["file_number"] = info.file_number
        header["year_recorded"] = info.year
        header["day_of_year"] = info.day_of_year
        header["hour_of_day"] = info.hour
        header["minute_of_hour"] = info.minute
        header["second_of_minute"] = info.second

        names = dtype.names or ()
        for key, value in self.header_overrides.binary_header.items():
            if key in names:
                header[key] = value

        return HeaderArray(np.asarray(HeaderArray(header).squeeze()))

    @property
    def sample(self) -> DataIndexer:
        """Trace sample indexer."""
        return self._sample_indexer

    @property
    def header(self) -> _LogicalHeaderIndexer:
        """Logical trace header indexer."""
        return _LogicalHeaderIndexer(self)

    @property
    def trace(self) -> _LogicalTraceIndexer:
        """Logical trace indexer."""
        return _LogicalTraceIndexer(self)

    def read_record_bytes(self, record_index: int = 0) -> bytes:
        """Read the full raw bytes of one RAW record (for rewrite)."""
        record = self.catalog.records[record_index]
        return bytes(
            record.fs.read_block(record.url, offset=0, length=record.file_size)
        )
