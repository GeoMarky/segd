"""Chunked sequential SEG-Y writer using :class:`segy.SegyFactory`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import BinaryIO

import numpy as np

from segd.segy.headers import project_headers_to_segy

if TYPE_CHECKING:
    from collections.abc import Iterator

    from segy import SegyFactory

    from segd.file import SegdFile

logger = logging.getLogger(__name__)


def iter_trace_chunks(
    num_traces: int,
    *,
    traces_per_chunk: int,
) -> Iterator[tuple[int, int]]:
    """Yield ``(start, stop)`` global index ranges for sequential chunks."""
    if traces_per_chunk <= 0:
        msg = f"traces_per_chunk must be positive, got {traces_per_chunk}"
        raise ValueError(msg)
    for start in range(0, num_traces, traces_per_chunk):
        stop = min(start + traces_per_chunk, num_traces)
        yield start, stop


def write_trace_chunks(  # noqa: PLR0913
    *,
    segd_file: SegdFile,
    factory: SegyFactory,
    fp: BinaryIO,
    traces_per_chunk: int,
    progress: bool = True,
) -> int:
    """Fetch SEG-D traces in chunks, project headers, and append SEG-Y bytes.

    Args:
        segd_file: Open SEG-D file supplying samples and logical headers.
        factory: SEG-Y factory used to encode trace headers and samples.
        fp: Binary file positioned at the first trace.
        traces_per_chunk: Number of traces fetched and written per iteration.
        progress: Show a tqdm progress bar when available.

    Returns:
        Number of traces written.
    """
    num_traces = segd_file.num_traces
    chunks = list(iter_trace_chunks(num_traces, traces_per_chunk=traces_per_chunk))

    iterable: Any = chunks
    if progress:
        try:
            from tqdm.auto import tqdm  # noqa: PLC0415

            iterable = tqdm(chunks, unit="chunk", desc="Writing SEG-Y traces")
        except ImportError:  # pragma: no cover
            logger.debug("tqdm not installed; writing without a progress bar")

    written = 0
    for start, stop in iterable:
        indices = np.arange(start, stop, dtype=np.int64)
        logical = np.atleast_1d(np.asarray(segd_file.header[indices]))
        samples = np.asarray(segd_file.sample.fetch(indices), dtype=np.float32)
        if samples.ndim == 1:
            samples = samples.reshape(1, -1)

        headers = factory.create_trace_header_template(len(indices))
        project_headers_to_segy(logical, headers)
        fp.write(factory.create_traces(headers, samples))
        written += len(indices)

    return written
