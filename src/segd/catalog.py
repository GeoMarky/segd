"""Multi-file RAW record catalog."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal

from fsspec.core import url_to_fs

from segd.config import RecordOrder
from segd.exceptions import SegdFileSpecMismatchError
from segd.inference import GeneralHeaderInfo
from segd.inference import infer_record

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fsspec import AbstractFileSystem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordEntry:
    """One demultiplexed SEG-D RAW record in a catalog."""

    url: str
    fs: AbstractFileSystem
    info: GeneralHeaderInfo
    global_trace_start: int
    file_size: int

    @property
    def num_traces(self) -> int:
        """Channels in this record."""
        return self.info.channels

    @property
    def trace_stride(self) -> int:
        """Bytes per demux trace (header + samples)."""
        return self.info.trace_header_size + self.info.samples * 4

    def local_offset(self, local_index: int) -> int:
        """Byte offset of a local channel index within the record."""
        return self.info.file_header_size + local_index * self.trace_stride


@dataclass
class RecordCatalog:
    """Ordered collection of RAW records exposed as a flat trace index."""

    records: list[RecordEntry]

    @property
    def num_traces(self) -> int:
        """Total traces across all records."""
        if not self.records:
            return 0
        last = self.records[-1]
        return last.global_trace_start + last.num_traces

    @property
    def num_records(self) -> int:
        """Number of RAW files."""
        return len(self.records)

    @property
    def urls(self) -> list[str]:
        """Record URLs in catalog order."""
        return [record.url for record in self.records]

    def locate(self, global_index: int) -> tuple[RecordEntry, int]:
        """Map a global trace index to (record, local_index)."""
        if global_index < 0 or global_index >= self.num_traces:
            msg = f"Trace index {global_index} out of range [0, {self.num_traces})."
            raise IndexError(msg)

        # Linear scan is fine for typical tape-sized catalogs; binary search if needed.
        for record in self.records:
            local = global_index - record.global_trace_start
            if 0 <= local < record.num_traces:
                return record, local

        msg = f"Failed to locate global trace {global_index}."
        raise IndexError(msg)


def collect_raw_urls(
    path: str | Path,
    *,
    pattern: str = "R*.RAW",
) -> list[str]:
    """List demux RAW files in a directory, skipping EOT markers."""
    directory = Path(path)
    return sorted(
        str(p)
        for p in directory.glob(pattern)
        if p.name.upper() != "EOT.RAW" and p.stat().st_size > 64
    )


def _sort_urls(
    urls: Sequence[str],
    infos: list[GeneralHeaderInfo],
    order: RecordOrder,
) -> list[int]:
    """Return indices that sort urls according to order."""
    indices = list(range(len(urls)))
    if order == RecordOrder.NAME:
        return sorted(indices, key=lambda i: Path(urls[i]).name)
    if order == RecordOrder.FFID:
        return sorted(indices, key=lambda i: infos[i].file_number)
    if order == RecordOrder.SHOT_POINT:

        def _shot_key(i: int) -> int:
            shot = infos[i].shot_point
            return shot if shot is not None else -1

        return sorted(indices, key=_shot_key)
    # RecordOrder.GIVEN (default)
    return indices


def build_catalog(
    urls: str | Sequence[str],
    *,
    storage_options: dict[str, object] | None = None,
    order: RecordOrder
    | Literal["given", "name", "ffid", "shot_point"] = RecordOrder.GIVEN,
) -> RecordCatalog:
    """Open and validate one or more RAW URLs into a RecordCatalog."""
    storage_options = storage_options or {}
    if isinstance(order, str):
        order = RecordOrder(order)

    url_list = [urls] if isinstance(urls, str) else list(urls)
    if not url_list:
        msg = "At least one RAW URL is required."
        raise ValueError(msg)

    parsed: list[tuple[str, AbstractFileSystem, GeneralHeaderInfo, int]] = []
    for url in url_list:
        fs, path = url_to_fs(url, **storage_options)
        info = infer_record(fs, path)
        file_size = int(fs.info(path)["size"])
        parsed.append((path, fs, info, file_size))

    order_idx = _sort_urls(
        [p[0] for p in parsed],
        [p[2] for p in parsed],
        order,
    )
    parsed = [parsed[i] for i in order_idx]

    ref = parsed[0][2]
    records: list[RecordEntry] = []
    cursor = 0
    for path, fs, info, file_size in parsed:
        if (
            info.channels != ref.channels
            or info.samples != ref.samples
            or info.sample_interval_us != ref.sample_interval_us
            or info.format_code != ref.format_code
            or info.trace_header_size != ref.trace_header_size
        ):
            msg = (
                f"Record {path} geometry mismatch versus first record: "
                f"channels/samples/interval/format/trace_header_size differ."
            )
            raise SegdFileSpecMismatchError(msg)

        records.append(
            RecordEntry(
                url=path,
                fs=fs,
                info=info,
                global_trace_start=cursor,
                file_size=file_size,
            )
        )
        cursor += info.channels

    logger.info(
        "Built RecordCatalog with %s records and %s traces.",
        len(records),
        cursor,
    )
    return RecordCatalog(records=records)
