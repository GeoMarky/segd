"""Registry for SEG-D standard specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from segd.schema import SegdSpec
    from segd.schema import SegdStandard

_REGISTRY: dict[SegdStandard, SegdSpec] = {}


def register_segd_standard(standard: SegdStandard, spec: SegdSpec) -> None:
    """Register a SEG-D standard profile."""
    _REGISTRY[standard] = spec


def get_segd_standard(standard: SegdStandard) -> SegdSpec:
    """Return a deep copy of a registered SEG-D standard."""
    try:
        return _REGISTRY[standard].model_copy(deep=True)
    except KeyError as err:
        known = ", ".join(str(k.value) for k in _REGISTRY)
        msg = f"Unknown SEG-D standard {standard!r}. Known: {known}"
        raise KeyError(msg) from err
