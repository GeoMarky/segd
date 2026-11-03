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


def test_add_field_overwrites_or_rejects_a_duplicate() -> None:
    header = HeaderSpec(
        fields=[HeaderField(name="a", format=ScalarType.INT16, byte=1)],
        item_size=8,
    )
    header.add_field(HeaderField(name="b", format=ScalarType.INT16, byte=3))
    header.add_field(
        HeaderField(name="a", format=ScalarType.INT32, byte=1),
        overwrite=True,
    )
    assert header.names.count("a") == 1
    with pytest.raises(KeyError, match="already exists"):
        header.add_field(HeaderField(name="b", format=ScalarType.INT16, byte=5))


def test_remove_field_rejects_an_unknown_name() -> None:
    header = HeaderSpec(fields=[HeaderField(name="a", format=ScalarType.INT16, byte=1)])
    with pytest.raises(KeyError, match="does not exist"):
        header.remove_field("missing")


def test_customize_rejects_overlapping_or_duplicate_replacements() -> None:
    header = HeaderSpec(fields=[HeaderField(name="a", format=ScalarType.INT16, byte=1)])
    with pytest.raises(ValueError, match="overlap"):
        header.customize(
            [
                HeaderField(name="c", format=ScalarType.INT32, byte=1),
                HeaderField(name="d", format=ScalarType.INT32, byte=2),
            ]
        )
    with pytest.raises(ValueError, match="Duplicate"):
        header.customize(
            [
                HeaderField(name="e", format=ScalarType.INT16, byte=1),
                HeaderField(name="e", format=ScalarType.INT16, byte=3),
            ]
        )


def test_empty_header_is_allowed_but_fields_must_fit() -> None:
    assert HeaderSpec(fields=[], item_size=4).fields == []
    with pytest.raises(ValueError, match="exceed"):
        HeaderSpec(
            fields=[HeaderField(name="a", format=ScalarType.INT32, byte=1)],
            item_size=2,
        )
