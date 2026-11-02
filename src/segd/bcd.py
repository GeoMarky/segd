"""Binary-coded decimal helpers for SEG-D headers."""

from __future__ import annotations


def bcd_nibble(value: int) -> int:
    """Decode a single BCD byte to an integer 0-99."""
    return ((value >> 4) & 0x0F) * 10 + (value & 0x0F)


def bcd_bytes(data: bytes | memoryview) -> int:
    """Decode a big-endian BCD byte sequence to an integer."""
    result = 0
    for byte in data:
        result = result * 100 + bcd_nibble(byte)
    return result


def encode_bcd_byte(value: int) -> int:
    """Encode an integer 0-99 as one BCD byte."""
    if value < 0 or value > 99:
        msg = f"BCD byte value out of range: {value}"
        raise ValueError(msg)
    return ((value // 10) << 4) | (value % 10)


def encode_bcd(value: int, length: int) -> bytes:
    """Encode an integer as big-endian BCD of fixed byte length."""
    digits = f"{value:0{length * 2}d}"
    if len(digits) > length * 2:
        msg = f"Value {value} does not fit in {length} BCD bytes."
        raise ValueError(msg)
    out = bytearray(length)
    for i in range(length):
        pair = int(digits[i * 2 : i * 2 + 2])
        out[i] = encode_bcd_byte(pair)
    return bytes(out)
