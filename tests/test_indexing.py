"""Indexing helper tests."""

from __future__ import annotations

import numpy as np
import pytest

from segd.indexing import bounds_check


def test_bounds_check_ok() -> None:
    bounds_check(np.asarray([0, 1, 2], dtype=np.int64), 3, "trace")


def test_bounds_check_raises() -> None:
    with pytest.raises(IndexError):
        bounds_check(np.asarray([-1], dtype=np.int64), 3, "trace")
    with pytest.raises(IndexError):
        bounds_check(np.asarray([3], dtype=np.int64), 3, "trace")
