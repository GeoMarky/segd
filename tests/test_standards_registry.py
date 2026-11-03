"""Standards registry tests."""

from __future__ import annotations

import pytest

from segd.schema import SegdStandard
from segd.standards import get_segd_standard


def test_get_demux_standard_is_copy() -> None:
    a = get_segd_standard(SegdStandard.DEMUX_8058)
    b = get_segd_standard(SegdStandard.DEMUX_8058)
    assert a is not b
    assert a.segd_standard == SegdStandard.DEMUX_8058
    assert a.endianness is not None


def test_unknown_standard_names_the_registered_profiles() -> None:
    with pytest.raises(KeyError, match="Unknown SEG-D"):
        get_segd_standard(SegdStandard.CUSTOM)
