"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from segd import SegdFactory
from segd.schema import HeaderField
from segd.schema import ScalarType

CASIE21_P190 = Path("/media/data/data/CASIE21/MGL2104/Seq014_MGL2104PD19.P190")
CASIE21_TAPE75 = Path("/media/data/data/CASIE21/MGL2104/tars/TAPE0075.REEL")
CASIE21_RAW1 = CASIE21_TAPE75 / "R037943_1623938836.RAW"
CASIE21_RAW2 = CASIE21_TAPE75 / "R037944_1623938853.RAW"


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "casie21: tests that require local CASIE21 survey files",
    )


@pytest.fixture
def mock_filesystem() -> str:
    """Session-scoped memory filesystem URL helper."""
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


@pytest.fixture
def casie21_paths() -> dict[str, Path]:
    """CASIE21 sample paths; skip if missing."""
    if not CASIE21_P190.exists() or not CASIE21_RAW1.exists():
        pytest.skip("CASIE21 sample data not available")
    return {
        "p190": CASIE21_P190,
        "raw1": CASIE21_RAW1,
        "raw2": CASIE21_RAW2,
        "tape75": CASIE21_TAPE75,
    }
