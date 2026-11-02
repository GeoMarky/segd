"""Base helpers for standard field enums."""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

from segd.schema.format import ScalarType
from segd.schema.header import HeaderField


class FieldTuple(NamedTuple):
    """Byte location and format for a standard field."""

    byte: int
    format: str  # noqa: A003


class SegStandardEnum(FieldTuple, Enum):
    """A special enum for defining standards with data model generation attribute."""

    @property
    def model(self) -> HeaderField:
        """Generate proper data model for header field with validation."""
        return HeaderField(
            name=self.name.lower(),
            byte=self.byte,
            format=ScalarType(self.format),
        )
