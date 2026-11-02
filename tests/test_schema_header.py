"""Tests for header schema."""

from __future__ import annotations

import pytest

from segd.schema import Endianness
from segd.schema import HeaderField
from segd.schema import HeaderSpec
from segd.schema import ScalarType


def test_header_field_offset() -> None:
    field = HeaderField(name="x", format=ScalarType.INT32, byte=9)
    assert field.offset == 8
    assert field.range == (9, 13)


def test_header_spec_dtype_with_gaps(basic_header_fields: list[HeaderField]) -> None:
    header = HeaderSpec(fields=basic_header_fields, endianness=Endianness.BIG)
    assert header.dtype.names == ("foo", "bar")
    assert header.dtype.itemsize == 6


def test_header_spec_item_size_padding(basic_header_fields: list[HeaderField]) -> None:
    header = HeaderSpec(
        fields=basic_header_fields,
        item_size=32,
        endianness=Endianness.BIG,
    )
    assert header.dtype.itemsize == 32


def test_duplicate_field_names_rejected() -> None:
    fields = [
        HeaderField(name="foo", format=ScalarType.INT16, byte=1),
        HeaderField(name="foo", format=ScalarType.INT16, byte=3),
    ]
    with pytest.raises(ValueError, match="Duplicate"):
        HeaderSpec(fields=fields)


def test_customize_overwrites_and_drops_overlaps() -> None:
    header = HeaderSpec(
        fields=[
            HeaderField(name="a", format=ScalarType.INT32, byte=1),
            HeaderField(name="b", format=ScalarType.INT16, byte=5),
        ]
    )
    header.customize(HeaderField(name="c", format=ScalarType.INT32, byte=3))
    assert "b" not in header.names
    assert "c" in header.names
