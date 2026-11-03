"""HeaderArray / TraceArray tests."""

from __future__ import annotations

import numpy as np
import pytest

from segd.arrays import HeaderArray
from segd.arrays import SegdArray
from segd.exceptions import InvalidFieldError


def test_header_array_to_dict_and_alias() -> None:
    dtype = np.dtype([("source_coord_x", ">i4"), ("group_coord_y", ">i4")])
    arr = HeaderArray(np.zeros(1, dtype=dtype))
    arr["source_coord_x"] = 10
    assert arr.to_dict()["source_coord_x"] == 10
    assert arr["sx"] == 10
    with pytest.raises(InvalidFieldError):
        _ = arr["not_a_field"]


def test_header_array_copy_json_and_dataframe() -> None:
    dtype = np.dtype([("source_coord_x", "<i4"), ("group_coord_y", "<i4")])
    arr = HeaderArray(np.zeros(2, dtype=dtype))
    copied = arr.copy()
    assert isinstance(copied, HeaderArray)

    copied["sx"] = 3
    copied[["sx", "gy"]] = (4, 5)
    assert int(copied["source_coord_x"][0]) == 4
    assert int(copied["group_coord_y"][0]) == 5
    assert "source_coord_x" in copied.to_json()
    assert len(copied.to_dataframe()) == 2


def test_unstructured_header_array_rejects_dict_conversion() -> None:
    plain = HeaderArray(np.arange(3))
    with pytest.raises(ValueError, match="structured"):
        plain.to_dict()
    plain[0] = 9
    assert int(plain[0]) == 9


def test_unknown_header_name_list_is_rejected() -> None:
    dtype = np.dtype([("source_coord_x", "<i4")])
    arr = HeaderArray(np.zeros(1, dtype=dtype))
    with pytest.raises(InvalidFieldError):
        _ = arr[["missing", "also"]]


def test_numpy_concatenate_accepts_plain_ndarray() -> None:
    dtype = np.dtype([("a", "<i4")])
    arr = SegdArray(np.ones(2, dtype=dtype))
    mixed = np.concatenate([arr, np.zeros(1, dtype=dtype)])
    assert mixed.shape == (3,)
