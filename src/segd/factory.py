"""Factory for creating SEG-D record bytes."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING
from typing import Any

import numpy as np
from fsspec.core import url_to_fs

from segd.bcd import encode_bcd
from segd.bcd import encode_bcd_byte
from segd.schema.segd import SegdStandard
from segd.standards import DEFAULT_DEMUX_TRACE_HEADER_SIZE
from segd.standards import get_segd_standard

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

    from segd.schema import SegdSpec


def get_default_text(
    line_name: str = "SEGD",
    shot_point: int = 1,
) -> str:
    """Create a short textual summary for external header."""
    return f"$11 SEGD line={line_name} shot={shot_point}"


class SegdFactory:
    """Build bytes for SEG-D demux records (format 8058).

    Writes go through the factory (same split as segy): create header/trace
    bytes, then write with fsspec. Unparsed header blocks from a template
    record can be supplied to preserve manufacturer extensions on rewrite.
    """

    def __init__(
        self,
        spec: SegdSpec | None = None,
        sample_interval: int = 2000,
        samples_per_trace: int = 7500,
        channels_per_record: int = 960,
        trace_header_size: int = DEFAULT_DEMUX_TRACE_HEADER_SIZE,
    ) -> None:
        self.spec = spec or get_segd_standard(SegdStandard.DEMUX_8058)
        self.sample_interval = sample_interval
        self.samples_per_trace = samples_per_trace
        self.channels_per_record = channels_per_record
        self.trace_header_size = trace_header_size

    def create_textual_header(
        self,
        text: str | None = None,
        line_name: str = "SEGD",
        shot_point: int = 1,
    ) -> bytes:
        """Create external-header-like text bytes (ASCII)."""
        body = text or get_default_text(line_name=line_name, shot_point=shot_point)
        return body.encode("ascii", errors="replace")

    def create_binary_header(  # noqa: PLR0913
        self,
        *,
        file_number: int = 1,
        shot_point: int = 1,
        year: int = 2021,
        day_of_year: int = 1,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        template_file_header: bytes | None = None,
    ) -> bytes:
        """Create a minimal demux 8058 file header, or patch a template.

        Args:
            file_number: Extended file number / FFID.
            shot_point: Shot point number stored in GH3.
            year: Four-digit year.
            day_of_year: Julian day.
            hour: Hour of day.
            minute: Minute of hour.
            second: Second of minute.
            template_file_header: Optional original file header to preserve
                manufacturer blocks; general header fields are overwritten.

        Returns:
            File header bytes (before first demux trace).
        """
        if template_file_header is not None:
            header = bytearray(template_file_header)
        else:
            # Minimal header: 3 GH + 1 CSD + padding to a small aligned size.
            header = bytearray(128)

        # GH1
        header[0:2] = b"\xff\xff"
        header[2:4] = encode_bcd(8058, 2)
        header[10] = encode_bcd_byte(year % 100)
        header[11] = (2 << 4) | (day_of_year // 100)
        header[12] = encode_bcd_byte(day_of_year % 100)
        header[13] = encode_bcd_byte(hour)
        header[14] = encode_bcd_byte(minute)
        header[15] = encode_bcd_byte(second)
        # Base scan interval in 1/16 ms units
        header[22] = int(round(self.sample_interval / 1000.0 * 16))
        header[27] = encode_bcd_byte(1)  # channel sets
        header[28] = 0  # skews
        header[29] = 0  # extended header length
        header[30] = 0  # external header length
        header[31] = 0xFF  # revision → see GH2

        # GH2: extended file number
        header[32:35] = file_number.to_bytes(3, "big")
        header[32 + 15 : 32 + 17] = struct.pack(
            ">H", int(self.samples_per_trace * self.sample_interval / 1000)
        )
        header[32 + 17 : 32 + 19] = struct.pack(">H", int(self.sample_interval / 1000))

        # GH3: shot point at bytes 10-11 (index 73-74)
        header[64:67] = file_number.to_bytes(3, "big")
        header[73:75] = struct.pack(">H", shot_point & 0xFFFF)

        # Channel set descriptor at offset 96
        csd_off = 96
        if len(header) < csd_off + 32:
            header.extend(bytearray(csd_off + 32 - len(header)))
        header[csd_off] = encode_bcd_byte(1)
        header[csd_off + 1] = encode_bcd_byte(1)
        header[csd_off + 4 : csd_off + 6] = struct.pack(">H", self.samples_per_trace)
        header[csd_off + 8 : csd_off + 10] = encode_bcd(self.channels_per_record, 2)

        return bytes(header)

    def create_trace_header(
        self,
        *,
        channel: int,
        file_number: int = 1,
        template: bytes | None = None,
    ) -> bytes:
        """Create one demux trace header."""
        if template is not None:
            th = bytearray(template)
            if len(th) < self.trace_header_size:
                th.extend(bytearray(self.trace_header_size - len(th)))
        else:
            th = bytearray(self.trace_header_size)

        th[0:2] = b"\xff\xff"
        th[2] = 1  # scan type
        th[3] = 1  # channel set
        # Trace number as BCD uint16
        th[4:6] = encode_bcd(channel, 2)
        th[16:20] = file_number.to_bytes(4, "big")
        return bytes(th[: self.trace_header_size])

    def create_traces(
        self,
        samples: NDArray[Any],
        *,
        file_number: int = 1,
        template_trace_headers: Sequence[bytes] | None = None,
    ) -> bytes:
        """Create demux trace bytes (headers + IEEE big-endian samples).

        Args:
            samples: Array shaped (channels, samples) or (samples,) for one channel.
            file_number: FFID stamped into each demux header.
            template_trace_headers: Optional per-channel original headers.

        Returns:
            Contiguous demux trace payload bytes.
        """
        array = np.asarray(samples, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if array.shape[0] != self.channels_per_record:
            msg = f"Expected {self.channels_per_record} channels, got {array.shape[0]}."
            raise ValueError(msg)
        if array.shape[1] != self.samples_per_trace:
            msg = f"Expected {self.samples_per_trace} samples, got {array.shape[1]}."
            raise ValueError(msg)

        # Big-endian sample payload
        be_samples = array.astype(">f4", copy=False)
        chunks: list[bytes] = []
        for channel in range(self.channels_per_record):
            template = None
            if template_trace_headers is not None:
                template = template_trace_headers[channel]
            th = self.create_trace_header(
                channel=channel + 1,
                file_number=file_number,
                template=template,
            )
            chunks.append(th)
            chunks.append(be_samples[channel].tobytes())
        return b"".join(chunks)

    def create_record(  # noqa: PLR0913
        self,
        samples: NDArray[Any],
        *,
        file_number: int = 1,
        shot_point: int = 1,
        year: int = 2021,
        day_of_year: int = 1,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        template_record: bytes | None = None,
    ) -> bytes:
        """Create a full RAW record (file header + demux traces).

        When ``template_record`` is provided, its file header and per-trace
        demux headers are preserved and only sample payloads are replaced.
        """
        template_file_header = None
        template_ths: list[bytes] | None = None
        if template_record is not None:
            # Infer header size from first demux magic
            magic = b"\xff\xff\x01\x01"
            offset = template_record.find(magic)
            if offset < 0:
                msg = "template_record missing demux trace magic."
                raise ValueError(msg)
            template_file_header = template_record[:offset]
            stride = self.trace_header_size + self.samples_per_trace * 4
            template_ths = []
            for i in range(self.channels_per_record):
                start = offset + i * stride
                template_ths.append(
                    template_record[start : start + self.trace_header_size]
                )

        file_header = self.create_binary_header(
            file_number=file_number,
            shot_point=shot_point,
            year=year,
            day_of_year=day_of_year,
            hour=hour,
            minute=minute,
            second=second,
            template_file_header=template_file_header,
        )
        # If using a template, keep exact original file header length/content
        # aside from GH field patches already applied.
        if template_file_header is not None:
            file_header = self.create_binary_header(
                file_number=file_number,
                shot_point=shot_point,
                year=year,
                day_of_year=day_of_year,
                hour=hour,
                minute=minute,
                second=second,
                template_file_header=template_file_header,
            )
            # Ensure same length as template
            if len(file_header) < len(template_file_header):
                file_header = file_header + template_file_header[len(file_header) :]
            file_header = file_header[: len(template_file_header)]

        traces = self.create_traces(
            samples,
            file_number=file_number,
            template_trace_headers=template_ths,
        )
        return file_header + traces

    def to_file(
        self,
        url: str,
        samples: NDArray[Any],
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Write a single RAW record to ``url``."""
        storage_options = kwargs.pop("storage_options", {})
        record = self.create_record(samples, **kwargs)
        fs, path = url_to_fs(url, **storage_options)
        with fs.open(path, mode="wb") as handle:
            handle.write(record)
