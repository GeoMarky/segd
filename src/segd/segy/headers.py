"""Project SEG-D logical headers onto a SEG-Y header template."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray


def project_headers_to_segy(
    logical_headers: NDArray[Any],
    segy_header_template: NDArray[Any],
) -> NDArray[Any]:
    """Copy intersecting field names from SEG-D logical headers into a SEG-Y template.

    Args:
        logical_headers: Structured array from :class:`~segd.file.SegdFile`.
        segy_header_template: Zeroed template from ``SegyFactory.create_trace_header_template``.

    Returns:
        Filled SEG-Y header array (same object as ``segy_header_template``).
    """
    src = np.atleast_1d(logical_headers)
    dst = segy_header_template
    if len(src) != len(dst):
        msg = f"Header length mismatch: logical={len(src)} segy_template={len(dst)}"
        raise ValueError(msg)

    src_names = set(src.dtype.names or ())
    for name in dst.dtype.names or ():
        if name in src_names:
            dst[name] = src[name]
    return dst
