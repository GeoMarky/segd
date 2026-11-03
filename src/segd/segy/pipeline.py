"""SEG-D → SEG-Y export pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal

from fsspec.core import url_to_fs
from segy import SegyFactory
from segy.schema import Endianness
from segy.schema import ScalarType
from segy.schema import SegyStandard
from segy.schema import TextHeaderEncoding
from segy.standards import get_segy_standard

from segd.catalog import resolve_raw_urls
from segd.config import SegdFileSettings
from segd.config import SegdHeaderOverrides
from segd.file import SegdFile
from segd.segy.writer import write_trace_chunks

if TYPE_CHECKING:
    from collections.abc import Sequence

    from segy.schema import SegySpec

    from segd.schema import SegdSpec

logger = logging.getLogger(__name__)

SampleFormatName = Literal["ieee", "ibm", "float32", "ibm32"]


def _resolve_output_path(output_path: Path | str, overwrite: bool) -> str:
    """Normalize output path and enforce overwrite policy for local paths."""
    as_str = str(output_path)
    candidate = Path(as_str)
    # Only apply exists-check for local filesystem paths.
    if "://" not in as_str and candidate.exists() and not overwrite:
        err = (
            f"Output location '{candidate.as_posix()}' exists. "
            "Set `overwrite=True` if intended."
        )
        raise FileExistsError(err)
    if "://" not in as_str:
        candidate.parent.mkdir(parents=True, exist_ok=True)
    return as_str


def resolve_sample_format(
    sample_format: SampleFormatName | ScalarType | str,
) -> ScalarType:
    """Map a user sample-format name to a :class:`~segy.schema.ScalarType`."""
    if isinstance(sample_format, ScalarType):
        if sample_format not in {ScalarType.FLOAT32, ScalarType.IBM32}:
            msg = f"Unsupported sample format: {sample_format}"
            raise ValueError(msg)
        return sample_format

    key = str(sample_format).strip().lower()
    if key in {"ieee", "float32", "ieee32"}:
        return ScalarType.FLOAT32
    if key in {"ibm", "ibm32"}:
        return ScalarType.IBM32
    msg = (
        f"Unknown sample_format '{sample_format}'. "
        "Use 'ieee' / 'float32' or 'ibm' / 'ibm32'."
    )
    raise ValueError(msg)


def build_default_segy_spec(
    *,
    sample_format: ScalarType,
    segy_spec: SegySpec | None = None,
) -> SegySpec:
    """Return a writable SEG-Y spec (REV1 by default) with encoding/endian/format set."""
    spec = (
        segy_spec.model_copy(deep=True)
        if segy_spec is not None
        else get_segy_standard(SegyStandard.REV1)
    )
    spec.endianness = Endianness.BIG
    spec.trace.data.format = sample_format
    if spec.text_header.encoding == TextHeaderEncoding.INFERRED:
        spec.set_text_header_encoding(TextHeaderEncoding.EBCDIC)
    return spec


def segd_to_segy(  # noqa: PLR0913
    raw_urls: str | Path | Sequence[str | Path] | None,
    output_path: str | Path,
    *,
    p190_path: str | Path | None = None,
    file_list: str | Path | None = None,
    file_prefix: str = "R",
    file_suffix: str = "RAW",
    file_pattern: str | None = None,
    segd_spec: SegdSpec | None = None,
    segy_spec: SegySpec | None = None,
    sample_format: SampleFormatName | ScalarType | str = "ieee",
    overwrite: bool = False,
    header_overrides: SegdHeaderOverrides | dict[str, Any] | None = None,
    settings: SegdFileSettings | None = None,
    progress: bool = True,
    traces_per_chunk: int | None = None,
) -> None:
    """Convert one or more SEG-D RAW records into a single SEG-Y file.

    Writes the textual and binary headers once, then appends trace chunks
    sequentially so sample volumes are never fully loaded into memory.

    ``FileExistsError`` is raised when a local output file exists and ``overwrite``
    is false. ``ValueError`` is raised when inputs or ``sample_format`` are invalid.

    Args:
        raw_urls: Single RAW URL, sequence of URLs/filenames, or a directory to scan.
            May be ``None`` when ``file_list`` supplies the inputs.
        output_path: Destination SEG-Y path (local or fsspec URL).
        p190_path: Optional UKOOA P1/90 navigation path for coordinate headers.
        file_list: Optional text file listing SEG-D filenames/paths (one per line).
        file_prefix: Directory-scan filename prefix (default ``R``).
        file_suffix: Directory-scan filename suffix (default ``RAW``).
        file_pattern: Optional explicit glob overriding prefix/suffix.
        segd_spec: Optional SEG-D specification (inferred when omitted).
        segy_spec: Optional SEG-Y specification (default REV1).
        sample_format: ``ieee`` (default) or ``ibm``.
        overwrite: Whether to overwrite an existing local output file.
        header_overrides: Optional fixed logical SEG-D header values on read.
        settings: :class:`~segd.config.SegdFileSettings` (endianness, storage, order).
        progress: Show a tqdm progress bar when available.
        traces_per_chunk: Trace batch size (default: channels in the first record).
    """
    settings = settings or SegdFileSettings()
    if header_overrides is not None and not isinstance(
        header_overrides, SegdHeaderOverrides
    ):
        header_overrides = SegdHeaderOverrides.model_validate(dict(header_overrides))

    urls = resolve_raw_urls(
        raw_urls,
        file_list=file_list,
        prefix=file_prefix,
        suffix=file_suffix,
        pattern=file_pattern,
    )
    out = _resolve_output_path(output_path, overwrite)

    navigation = str(p190_path) if p190_path is not None else None
    segd_file = SegdFile(
        urls,
        spec=segd_spec,
        settings=settings,
        header_overrides=header_overrides,
        navigation=navigation,
    )

    fmt = resolve_sample_format(sample_format)
    spec = build_default_segy_spec(sample_format=fmt, segy_spec=segy_spec)
    factory = SegyFactory(
        spec,
        sample_interval=segd_file.sample_interval,
        samples_per_trace=segd_file.samples_per_trace,
    )

    chunk = traces_per_chunk
    if chunk is None:
        chunk = segd_file.catalog.records[0].num_traces

    text_lines = [
        "C01 SEG-Y written by segd.segy.segd_to_segy",
        "C02 Source format: SEG-D demux 8058",
        f"C03 Sample format: {fmt.value}",
        f"C04 Number of input RAW records: {segd_file.num_records}",
        f"C05 Traces: {segd_file.num_traces}",
        f"C06 Samples/trace: {segd_file.samples_per_trace}",
        f"C07 Sample interval (us): {segd_file.sample_interval}",
        f"C08 P190: {navigation or 'none'}",
    ]
    while len(text_lines) < 39:
        text_lines.append(f"C{len(text_lines) + 1:02}")
    text_lines.append("C40 END TEXTUAL HEADER")
    text = "\n".join(line[:80].ljust(80) for line in text_lines)

    binary_update: dict[str, Any] = {
        "measurement_system_code": 1,  # metres
    }

    storage_options = settings.storage_options or {}
    fs, path = url_to_fs(out, **storage_options)
    logger.info(
        "Writing SEG-Y to %s (%s traces, chunk=%s, format=%s)",
        out,
        segd_file.num_traces,
        chunk,
        fmt.value,
    )
    with fs.open(path, mode="wb") as fp:
        fp.write(factory.create_textual_header(text))
        fp.write(factory.create_binary_header(update=binary_update))
        written = write_trace_chunks(
            segd_file=segd_file,
            factory=factory,
            fp=fp,
            traces_per_chunk=chunk,
            progress=progress,
        )

    logger.info("Wrote %s traces to %s", written, out)
