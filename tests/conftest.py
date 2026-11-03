"""Shared pytest fixtures."""

from __future__ import annotations

import numpy as np
import pytest

from segd import SegdFactory
from segd.schema import HeaderField
from segd.schema import ScalarType


@pytest.fixture
def mock_filesystem() -> str:
    """Memory filesystem URL helper."""
    return "memory://"


@pytest.fixture
def basic_header_fields() -> list[HeaderField]:
    """Minimal header fields for schema tests."""
    return [
        HeaderField(name="foo", format=ScalarType.INT32, byte=1),
        HeaderField(name="bar", format=ScalarType.INT16, byte=5),
    ]


@pytest.fixture
def tiny_segd_record(mock_filesystem: str) -> str:
    """Write a tiny 8058 record into memory and return its URL."""
    factory = SegdFactory(
        samples_per_trace=8,
        channels_per_record=4,
        sample_interval=2000,
        trace_header_size=248,
    )
    samples = np.arange(32, dtype=np.float32).reshape(4, 8)
    url = f"{mock_filesystem}tiny.RAW"
    factory.to_file(
        url, samples, file_number=100, shot_point=55, year=2021, day_of_year=10
    )
    return url
