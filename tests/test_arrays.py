"""HeaderArray / TraceArray tests."""

from __future__ import annotations

import numpy as np
import pytest

from segd.arrays import HeaderArray
from segd.exceptions import InvalidFieldError


def test_header_array_to_dict_and_alias() -> None:
    dtype = np.dtype([("source_coord_x", ">i4"), ("group_coord_y", ">i4")])
    arr = HeaderArray(np.zeros(1, dtype=dtype))
    arr["source_coord_x"] = 10
    assert arr.to_dict()["source_coord_x"] == 10
    assert arr["sx"] == 10
    with pytest.raises(InvalidFieldError):
        _ = arr["not_a_field"]
