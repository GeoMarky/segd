"""BCD helper tests."""

from __future__ import annotations

import pytest

from segd.bcd import bcd_bytes
from segd.bcd import bcd_nibble
from segd.bcd import encode_bcd
from segd.bcd import encode_bcd_byte


def test_bcd_roundtrip() -> None:
    assert bcd_nibble(0x21) == 21
    assert encode_bcd_byte(21) == 0x21
    assert bcd_bytes(encode_bcd(8058, 2)) == 8058
    assert bcd_bytes(encode_bcd(960, 2)) == 960


def test_encode_bcd_rejects_values_that_do_not_fit() -> None:
    with pytest.raises(ValueError, match="out of range"):
        encode_bcd_byte(100)
    with pytest.raises(ValueError, match="does not fit"):
        encode_bcd(1000, 1)
