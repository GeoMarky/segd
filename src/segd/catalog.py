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


def _normalize_file_suffix(suffix: str) -> str:
    """Strip a leading dot from a file suffix."""
    return suffix[1:] if suffix.startswith(".") else suffix


def collect_raw_urls(
    path: str | Path,
    *,
    prefix: str = "R",
    suffix: str = "RAW",
    pattern: str | None = None,
) -> list[str]:
    """List demux SEG-D files in a directory, skipping EOT markers.

    Args:
        path: Directory to scan.
        prefix: Filename prefix used when ``pattern`` is omitted (default ``R``).
        suffix: Filename extension without requiring a leading dot (default ``RAW``).
        pattern: Optional explicit glob. When omitted, uses ``{prefix}*.{suffix}``.
    """
    directory = Path(path)
    suffix = _normalize_file_suffix(suffix)
    glob_pattern = pattern if pattern is not None else f"{prefix}*.{suffix}"
    eot_name = f"EOT.{suffix}".upper()
    return sorted(
        str(p)
        for p in directory.glob(glob_pattern)
        if p.name.upper() != eot_name and p.stat().st_size > 64
    )


def read_file_list(
    file_list: str | Path,
    *,
    base_dir: str | Path | None = None,
) -> list[str]:
    """Read SEG-D filenames/paths from a text file (one entry per line).

    Blank lines and ``#`` comments are ignored. Relative paths resolve against
    ``base_dir`` when provided, otherwise against the file-list's parent directory.
    """
    list_path = Path(file_list)
    root = Path(base_dir) if base_dir is not None else list_path.parent
    urls: list[str] = []
    for raw_line in list_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        candidate = Path(line)
        if candidate.is_absolute():
            urls.append(str(candidate))
        else:
            urls.append(str(root / candidate))
    if not urls:
        msg = f"File list '{list_path}' did not contain any filenames."
        raise ValueError(msg)
    return urls


def resolve_raw_urls(
    raw_urls: str | Path | Sequence[str | Path] | None = None,
    *,
    file_list: str | Path | None = None,
    prefix: str = "R",
    suffix: str = "RAW",
    pattern: str | None = None,
) -> list[str]:
    """Resolve SEG-D inputs from a directory, explicit paths, or a filename list.

    Precedence:
        1. ``file_list`` — text file of names/paths (relative names use ``raw_urls``
           as the base directory when it is a directory).
        2. Directory ``raw_urls`` — glob with ``prefix`` / ``suffix`` (or ``pattern``).
        3. Sequence of paths — used as-is.
        4. Single file path — wrapped as a one-element list.
    """
    if file_list is not None:
        base_dir: str | Path | None = None
        if raw_urls is not None and isinstance(raw_urls, (str, Path)):
            candidate = Path(raw_urls)
            if candidate.is_dir():
                base_dir = candidate
        return read_file_list(file_list, base_dir=base_dir)

    if raw_urls is None:
        msg = "Provide raw_urls and/or file_list."
        raise ValueError(msg)

    if isinstance(raw_urls, (str, Path)):
        as_str = str(raw_urls)
        candidate = Path(as_str)
        if candidate.is_dir():
            return collect_raw_urls(
                candidate, prefix=prefix, suffix=suffix, pattern=pattern
            )
        return [as_str]
    return [str(u) for u in raw_urls]


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
