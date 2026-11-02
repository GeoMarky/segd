"""Transform pipeline tests."""

from __future__ import annotations

import numpy as np

from segd.transforms import ScaleTransform
from segd.transforms import TransformPipeline


def test_scale_transform_pipeline() -> None:
    data = np.arange(4, dtype=np.float64)
    pipeline = TransformPipeline()
    pipeline.add(ScaleTransform(scale=2.0, copy=True))
    out = pipeline.apply(data)
    np.testing.assert_array_equal(out, data * 2)
