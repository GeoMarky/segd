"""Transform pipeline tests."""

from __future__ import annotations

import numpy as np
import pytest

from segd.schema import Endianness
from segd.transforms import ByteSwapTransform
from segd.transforms import ScaleTransform
from segd.transforms import TransformFactory
from segd.transforms import TransformPipeline
from segd.transforms import get_endianness


def test_scale_transform_pipeline() -> None:
    data = np.arange(4, dtype=np.float64)
    pipeline = TransformPipeline()
    pipeline.add(ScaleTransform(scale=2.0, copy=True))
    out = pipeline.apply(data)
    np.testing.assert_array_equal(out, data * 2)


def test_get_endianness_for_native_and_big_endian() -> None:
    native = np.arange(4, dtype=np.int32)
    assert get_endianness(native) in {Endianness.LITTLE, Endianness.BIG}
    assert get_endianness(native.astype(">i4")) is Endianness.BIG


def test_byte_swap_skips_unknown_field_names() -> None:
    data = np.zeros(2, dtype=[("a", "<i4"), ("b", "<i4")])
    data["a"] = 1
    out = ByteSwapTransform(keys=["a", "missing"], copy=True).apply(data)
    assert out["a"].dtype.byteorder in {">", "="}


def test_scale_transform_on_a_plain_array() -> None:
    scaled = ScaleTransform(3.0).apply(np.arange(2, dtype=np.float64))
    np.testing.assert_array_equal(scaled, [0, 3])


def test_transform_factory_creates_and_rejects_names() -> None:
    assert isinstance(TransformFactory.create("byte_swap"), ByteSwapTransform)
    with pytest.raises(KeyError, match="Unknown transform"):
        TransformFactory.create("nope")
