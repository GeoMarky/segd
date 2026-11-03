"""Public navigation re-exports."""

from __future__ import annotations

from segd import navigation
from segd.p190 import P190File


def test_navigation_module_reexports_p190_types() -> None:
    assert navigation.P190File is P190File
    assert set(navigation.__all__) >= {"P190File", "ShotGather"}
