"""Specification representing header fields and headers."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from segd.schema.base import BaseDataType
from segd.schema.base import Endianness
from segd.schema.format import ScalarType  # noqa: TCH001


def _validate_non_overlapping_fields(fields: list[HeaderField]) -> None:
    """Validate that HeaderField list has unique names and no overlaps."""
    names = [field.name for field in fields]
    if len(names) != len(set(names)):
        msg = f"Duplicate header field names detected: {names}!"
        raise ValueError(msg)

    ranges = [field.range for field in fields]
    ranges.sort(key=lambda range_tuple: range_tuple[0])

    for i in range(len(ranges) - 1):
        if ranges_overlap(ranges[i], ranges[i + 1]):
            msg = f"Header fields overlap: {ranges[i]} and {ranges[i + 1]}!"
            raise ValueError(msg)


def ranges_overlap(range1: tuple[int, int], range2: tuple[int, int]) -> bool:
    """Checks if two right half-open ranges overlap."""
    return range1[0] < range2[1] and range1[1] > range2[0]


class HeaderField(BaseDataType):
    """A class representing header field spec."""

    name: str = Field(..., description="The short name of the field.")
    byte: int = Field(..., ge=1, description="Field's start byte location.")
    format: ScalarType = Field(..., description="The data type of the field.")  # noqa: A003

    @property
    def offset(self) -> int:
        """Return zero based offset from one based byte location."""
        return self.byte - 1

    @property
    def dtype(self) -> np.dtype[Any]:
        """Converts the data type of the object into a NumPy dtype."""
        return self.format.dtype

    @property
    def range(self) -> tuple[int, int]:
        """Return the start and stop byte location of the field."""
        return self.byte, self.byte + self.dtype.itemsize


class HeaderSpec(BaseDataType):
    """A class representing a header specification."""

    fields: list[HeaderField] = Field(
        ..., description="List containing multiple header field spec instances."
    )
    item_size: int | None = Field(
        default=None, description="Expected size of the struct."
    )
    offset: int | None = Field(default=None, ge=0, description="Starting byte offset.")

    endianness: Endianness | None = Field(
        default=None, description="Endianness of structured data type."
    )

    @property
    def dtype(self) -> np.dtype[Any]:
        """Converts the names, data types, and offsets into a NumPy dtype."""
        dtype_conf = {
            "names": self.names,
            "formats": self.formats,
            "offsets": self.offsets,
        }

        if self.item_size is not None:
            dtype_conf["itemsize"] = self.item_size

        struct_dtype = np.dtype(dtype_conf)  # type: ignore[call-overload]

        if self.endianness is not None:
            struct_dtype = struct_dtype.newbyteorder(self.endianness.symbol)

        return struct_dtype  # type: ignore[no-any-return]

    @property
    def names(self) -> list[str]:
        """Get the names of the fields."""
        return [field.name for field in self.fields]

    @property
    def formats(self) -> list[np.dtype[Any]]:
        """Get the formats of the fields."""
        return [field.dtype for field in self.fields]

    @property
    def offsets(self) -> list[int]:
        """Get the offsets the fields."""
        return [field.offset for field in self.fields]

    @field_validator("fields")
    @classmethod
    def ensure_no_duplicate_fields(
        cls: type[HeaderSpec], fields: list[HeaderField]
    ) -> list[HeaderField]:
        """Check if fields are unique and error out if not."""
        name_counter = Counter(field.name for field in fields)
        duplicates = [name for name, count in name_counter.items() if count > 1]

        if duplicates:
            msg = f"Duplicate header fields detected: {', '.join(duplicates)}."
            raise ValueError(msg)

        return fields

    @model_validator(mode="after")
    def ensure_offsets_in_itemsize_bounds(self) -> HeaderSpec:
        """Ensure fields don't go above the allowed itemsize."""
        if len(self.fields) == 0:
            return self

        max_field = max(self.fields, key=lambda field: field.offset)

        if self.item_size is None:
            return self

        if max_field.offset + max_field.dtype.itemsize > self.item_size:
            msg = "Offsets exceed allowed header size."
            raise ValueError(msg)

        return self

    def add_field(self, field: HeaderField, overwrite: bool = False) -> None:
        """Add a field to the structured data type."""
        if field.name in self.names and overwrite is False:
            msg = (
                f"Field named {field.name} already exists. If you wish to "
                "overwrite an existing field, pass `overwrite=True`."
            )
            raise KeyError(msg)

        if field.name not in self.names:
            self.fields.append(field)
        else:
            field_idx = self.names.index(field.name)
            self.fields[field_idx] = field

        self.fields = self.fields

    def remove_field(self, name: str) -> None:
        """Remove a field from the structured data type by name."""
        try:
            field_idx = self.names.index(name)
        except ValueError as err:
            msg = f"Field named {name} does not exist."
            raise KeyError(msg) from err

        del self.fields[field_idx]

    def customize(self, fields: HeaderField | list[HeaderField]) -> None:
        """Customize existing HeaderSpec fields with new headers handling overlaps."""
        if isinstance(fields, HeaderField):
            fields = [fields]

        _validate_non_overlapping_fields(fields)

        for field in fields:
            self.add_field(field, overwrite=True)

        fields_to_remove = set()
        for new_field in fields:
            for field in self.fields:
                does_overlap = ranges_overlap(field.range, new_field.range)
                if field.name != new_field.name and does_overlap:
                    fields_to_remove.add(field.name)

        for name in fields_to_remove:
            self.remove_field(name)
