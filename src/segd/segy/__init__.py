"""Optional SEG-D → SEG-Y export (requires ``segd[segy]``)."""

from __future__ import annotations

try:
    import segy as _segy  # noqa: F401
except ImportError as exc:  # pragma: no cover
    msg = (
        "The SEG-Y export extra is not installed. "
        "Install with: uv pip install -e '.[segy]'  "
        "or: uv sync --extra segy"
    )
    raise ImportError(msg) from exc

from segd.segy.pipeline import segd_to_segy

__all__ = ["segd_to_segy"]
