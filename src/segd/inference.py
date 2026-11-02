"""Infer SEG-D record layout and metadata from general headers."""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

from segd.bcd import bcd_bytes
from segd.bcd import bcd_nibble
from segd.exceptions import SegdFileSpecMismatchError
from segd.exceptions import UnsupportedFormatError
from segd.schema.segd import SegdStandard

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem

logger = logging.getLogger(__name__)

DEMUX_TRACE_MAGIC = b"\xff\xff\x01\x01"
SUPPORTED_FORMATS = {8058}


@dataclass(frozen=True)
class GeneralHeaderInfo:
    """Parsed general-header / channel-set summary for one RAW record."""

    format_code: int
    file_number: int
    year: int
    day_of_year: int
    hour: int
    minute: int
    second: int
    manufacturer_code: int
    additional_gh_blocks: int
    channels: int
    samples: int
    sample_interval_us: int
    shot_point: int | None
    record_length_ms: int | None
    raw_general_headers: bytes
    file_header_size: int
    trace_header_size: int
    external_header_text: str


def _parse_gh1(gh1: bytes) -> tuple[int, int, int, int, int, int, int, int, int]:
    """Parse general header block 1 fields used by this library."""
    format_code = bcd_bytes(gh1[2:4])
    year = 2000 + bcd_nibble(gh1[10])
    additional = gh1[11] >> 4
    day = (gh1[11] & 0x0F) * 100 + bcd_nibble(gh1[12])
    hour = bcd_nibble(gh1[13])
    minute = bcd_nibble(gh1[14])
    second = bcd_nibble(gh1[15])
    manufacturer = gh1[16]
    # Base scan interval: units of 1/16 ms for many Rev2/3 files.
    base_scan = gh1[22]
    sample_interval_us = int(round((base_scan / 16.0) * 1000.0)) if base_scan else 0
    return (
        format_code,
        year,
        additional,
        day,
        hour,
        minute,
        second,
        manufacturer,
        sample_interval_us,
    )


def _parse_channel_set(csd: bytes) -> tuple[int, int]:
    """Parse channel count (BCD) and sample count from a 32-byte channel set."""
    channels = bcd_bytes(csd[8:10])
    samples = struct.unpack(">H", csd[4:6])[0]
    return channels, samples


def _find_first_demux_trace(buffer: bytes, search_from: int = 0) -> int:
    """Return byte offset of the first demux trace header magic."""
    idx = buffer.find(DEMUX_TRACE_MAGIC, search_from)
    if idx < 0:
        msg = "Could not locate demultiplexed SEG-D trace headers (FFFF0101)."
        raise SegdFileSpecMismatchError(msg)
    return idx


def _external_text(file_header: bytes) -> str:
    """Extract printable external-header text if present."""
    marker = file_header.find(b"$11")
    if marker < 0:
        # Fall back to any long ASCII run
        text = "".join(chr(b) if 32 <= b < 127 else "\n" for b in file_header)
        parts = [p.strip() for p in text.split("\n") if len(p.strip()) > 20]
        return "\n".join(parts[:20])
    end = file_header.find(b"\x00", marker)
    if end < 0:
        end = min(len(file_header), marker + 512)
    return file_header[marker:end].decode("ascii", errors="replace")


def parse_record_headers(buffer: bytes, file_size: int) -> GeneralHeaderInfo:
    """Parse SEG-D record headers from an in-memory buffer (at least GH + CSD)."""
    if len(buffer) < 128:
        msg = "SEG-D buffer too small to contain general headers."
        raise SegdFileSpecMismatchError(msg)

    gh1 = buffer[0:32]
    (
        format_code,
        year,
        additional,
        day,
        hour,
        minute,
        second,
        manufacturer,
        sample_interval_us,
    ) = _parse_gh1(gh1)

    if format_code not in SUPPORTED_FORMATS:
        msg = f"Unsupported SEG-D format code {format_code}. Supported: {sorted(SUPPORTED_FORMATS)}"
        raise UnsupportedFormatError(msg)

    n_gh = 1 + additional
    gh_bytes = buffer[0 : n_gh * 32]
    csd_offset = n_gh * 32
    csd = buffer[csd_offset : csd_offset + 32]
    channels, samples = _parse_channel_set(csd)

    # Extended file number / shot point from GH2 / GH3 when present.
    file_number = bcd_bytes(gh1[0:2]) if gh1[0:2] != b"\xff\xff" else 0
    shot_point: int | None = None
    record_length_ms: int | None = None
    if n_gh >= 2:
        gh2 = buffer[32:64]
        file_number = int.from_bytes(gh2[0:3], "big")
        # Common Sercel layout: record length (ms) and sample interval (ms)
        record_length_ms = struct.unpack(">H", gh2[15:17])[0]
        interval_ms = struct.unpack(">H", gh2[17:19])[0]
        if interval_ms > 0:
            sample_interval_us = interval_ms * 1000
    if n_gh >= 3:
        gh3 = buffer[64:96]
        # Shot point stored as uint16 at bytes 10-11 of GH3 in CASIE21
        candidate = struct.unpack(">H", gh3[9:11])[0]
        if candidate > 0:
            shot_point = candidate

    if sample_interval_us <= 0:
        sample_interval_us = 2000

    # Prefer scanning for demux magic to get exact file header / TH sizes.
    # Need enough of the file; caller should pass at least header + one trace.
    sample_bytes = samples * 4
    # Lower bound on file header before traces
    min_header = csd_offset + 32
    first_trace = _find_first_demux_trace(buffer, search_from=min_header)
    remaining = file_size - first_trace
    if channels <= 0 or remaining % channels != 0:
        msg = (
            f"File size {file_size} incompatible with {channels} channels "
            f"after header offset {first_trace}."
        )
        raise SegdFileSpecMismatchError(msg)

    stride = remaining // channels
    trace_header_size = stride - sample_bytes
    if trace_header_size <= 0:
        msg = f"Computed non-positive trace header size ({trace_header_size})."
        raise SegdFileSpecMismatchError(msg)

    # Validate second trace magic when buffer is long enough
    if (
        first_trace + stride + 4 <= len(buffer)
        and buffer[first_trace + stride : first_trace + stride + 4] != DEMUX_TRACE_MAGIC
    ):
        logger.warning("Second demux trace magic mismatch; layout may be unusual.")

    external_text = _external_text(buffer[:first_trace])

    return GeneralHeaderInfo(
        format_code=format_code,
        file_number=file_number,
        year=year,
        day_of_year=day,
        hour=hour,
        minute=minute,
        second=second,
        manufacturer_code=manufacturer,
        additional_gh_blocks=additional,
        channels=channels,
        samples=samples,
        sample_interval_us=sample_interval_us,
        shot_point=shot_point,
        record_length_ms=record_length_ms,
        raw_general_headers=gh_bytes + csd,
        file_header_size=first_trace,
        trace_header_size=trace_header_size,
        external_header_text=external_text,
    )


def infer_record(
    fs: AbstractFileSystem,
    url: str,
) -> GeneralHeaderInfo:
    """Read enough of a RAW file to infer its SEG-D layout."""
    info = fs.info(url)
    file_size = int(info["size"])
    # Read up to 256 KiB for headers + first demux magic, then maybe more.
    probe = min(file_size, 262_144)
    buffer = fs.read_block(url, offset=0, length=probe)
    try:
        return parse_record_headers(buffer, file_size)
    except SegdFileSpecMismatchError:
        # Rare: demux magic beyond probe; read full file header guess of 64KiB more
        if probe >= file_size:
            raise
        buffer = fs.read_block(url, offset=0, length=min(file_size, 2_097_152))
        return parse_record_headers(buffer, file_size)


def standard_from_format(format_code: int) -> SegdStandard:
    """Map a format code to a SegdStandard enum."""
    if format_code == 8058:
        return SegdStandard.DEMUX_8058
    msg = f"No SegdStandard registered for format {format_code}."
    raise UnsupportedFormatError(msg)
