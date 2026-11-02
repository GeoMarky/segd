"""Data model implementations for trace specification."""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import Field
from pydantic import model_validator

from segd.schema.base import BaseDataType
from segd.schema.base import Endianness
from segd.schema.format import ScalarType  # noqa: TC001
from segd.schema.header import HeaderSpec  # noqa: TC001


class TraceDataSpec(BaseDataType):
    """A spec class for trace data (samples)."""

    format: ScalarType = Field(..., description="Format of trace samples.")  # noqa: A003
    samples: int | None = Field(
        default=None,
        description="Number of samples in trace.",
    )
    interval: int | None = Field(default=None, description="Sample interval of traces")

    @property
    def dtype(self) -> np.dtype[Any]:
        """Get numpy dtype with # of samples."""
        dtype = (self.format.dtype, (self.samples,))
        return np.dtype(dtype)


class TraceSpec(BaseDataType):
    """A spec class for a trace (header + data)."""

    header: HeaderSpec = Field(..., description="Trace header spec.")
    data: TraceDataSpec = Field(..., description="Trace data spec.")
    offset: int | None = Field(
        default=None, description="Starting offset of the first trace in a record."
    )
    endianness: Endianness | None = Field(
        default=None, description="Endianness of traces and headers."
    )
    count: int | None = Field(default=None, ge=0, description="Number of traces.")

    @model_validator(mode="after")
    def update_submodel_endianness(self) -> TraceSpec:
        """Ensure that submodel endianness matches the trace endianness."""
        self.header.endianness = self.endianness
        return self

    @property
    def dtype(self) -> np.dtype[Any]:
        """Get numpy dtype."""
        header_dtype = self.header.dtype
        data_dtype = self.data.dtype

        trace_dtype = np.dtype([("header", header_dtype), ("data", data_dtype)])

        if self.endianness is not None:
            trace_dtype = trace_dtype.newbyteorder(self.endianness.symbol)

        return trace_dtype
