"""SEG-D parser configuration."""

from __future__ import annotations

from collections.abc import Mapping  # noqa: TCH003
from enum import StrEnum
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from segd.schema import Endianness  # noqa: TCH001


class RecordOrder(StrEnum):
    """How to order a list of RAW record URLs."""

    GIVEN = "given"
    NAME = "name"
    FFID = "ffid"
    SHOT_POINT = "shot_point"


class SegdBaseSettings(BaseSettings):
    """Base class for settings."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)


class SegdHeaderOverrides(SegdBaseSettings):
    """SEG-D header parsing overrides."""

    binary_header: Mapping[str, int | float] = Field(
        default_factory=dict,
        description="Header fields to override in binary header during read.",
    )
    trace_header: Mapping[str, int | float] = Field(
        default_factory=dict,
        description="Header fields to override in trace headers during read.",
    )
    model_config = SettingsConfigDict(env_prefix="SEGD_OVERRIDE_")


class SegdFileSettings(SegdBaseSettings):
    """SEG-D file parsing settings."""

    endianness: Endianness | None = Field(
        default=None,
        description="Override the inferred endianness of the file.",
    )
    storage_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Storage options to pass to the storage backend.",
    )
    order: RecordOrder = Field(
        default=RecordOrder.GIVEN,
        description="Ordering for multi-file RAW lists.",
    )
    model_config = SettingsConfigDict(env_prefix="SEGD_")
