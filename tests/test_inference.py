"""SEG-D header inference error paths."""

from __future__ import annotations

import pytest

from segd.exceptions import SegdFileSpecMismatchError
from segd.exceptions import UnsupportedFormatError
from segd.inference import _external_text
from segd.inference import parse_record_headers
from segd.inference import standard_from_format


def test_parse_record_headers_rejects_a_short_buffer() -> None:
    with pytest.raises(SegdFileSpecMismatchError, match="too small"):
        parse_record_headers(b"\x00" * 10, 10)


def test_external_text_falls_back_to_long_ascii_and_stops_at_a_null() -> None:
    assert _external_text(b"short") == ""
    assert _external_text(b"A" * 30) == "A" * 30
    assert _external_text(b"$11 hello").startswith("$11")
    assert "tail" not in _external_text(b"$11 hello\x00tail")


def test_standard_from_format_rejects_an_unregistered_code() -> None:
    with pytest.raises(UnsupportedFormatError):
        standard_from_format(1)
