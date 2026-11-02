"""BCD helper tests."""

from __future__ import annotations

from segd.bcd import bcd_bytes
from segd.bcd import bcd_nibble
from segd.bcd import encode_bcd
from segd.bcd import encode_bcd_byte


def test_bcd_roundtrip() -> None:
    assert bcd_nibble(0x21) == 21
    assert encode_bcd_byte(21) == 0x21
    assert bcd_bytes(encode_bcd(8058, 2)) == 8058
    assert bcd_bytes(encode_bcd(960, 2)) == 960
