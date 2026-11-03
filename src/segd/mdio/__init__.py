"""Optional SEG-D + P190 → MDIO ingest (requires ``segd[mdio]``)."""

from __future__ import annotations

try:
    import mdio as _mdio  # noqa: F401
except ImportError as exc:  # pragma: no cover
    msg = (
        "The MDIO ingest extra is not installed. "
        "Install with: uv pip install -e '.[mdio]'  "
        "(requires Python >=3.12)."
    )
    raise ImportError(msg) from exc

from segd.mdio.pipeline import segd_to_mdio

__all__ = ["segd_to_mdio"]
