"""Data model implementations for SEG-D file spec."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field
from pydantic import model_validator

from segd.schema.base import CamelCaseModel
from segd.schema.base import Endianness
from segd.schema.header import HeaderField  # noqa: TC001
from segd.schema.header import HeaderSpec  # noqa: TC001
from segd.schema.trace import TraceDataSpec  # noqa: TC001
from segd.schema.trace import TraceSpec  # noqa: TC001


class SegdStandard(StrEnum):
    """Allowed values for SEG-D standards in SegdSpec."""

    CUSTOM = "custom"
    DEMUX_8058 = "8058"


class SegdSpec(CamelCaseModel):
    """A class defining a SEG-D file / record spec."""

    segd_standard: SegdStandard = Field(..., description="Base SEG-D format profile.")
    binary_header: HeaderSpec = Field(..., description="Logical binary header spec.")
    trace: TraceSpec = Field(..., description="Trace header + data spec.")
    text_header: str | None = Field(
        default=None, description="Optional textual summary / external header text."
    )

    endianness: Endianness | None = Field(
        default=None, description="Endianness of SEG-D file."
    )

    # Physical layout (filled during open / inference)
    file_header_size: int | None = Field(
        default=None, description="Bytes before first demux trace in a record."
    )
    channels_per_record: int | None = Field(
        default=None, description="Number of channels (traces) per RAW record."
    )

    @model_validator(mode="after")
    def update_submodel_endianness(self) -> SegdSpec:
        """Ensure that submodel endianness matches the SEG-D endianness."""
        self.binary_header.endianness = self.endianness
        self.trace.endianness = self.endianness
        return self

    def customize(
        self: SegdSpec,
        binary_header_fields: list[HeaderField] | None = None,
        trace_header_fields: list[HeaderField] | None = None,
        trace_data_spec: TraceDataSpec | None = None,
    ) -> SegdSpec:
        """Customize an existing SEG-D spec.

        Args:
            binary_header_fields: List of custom binary header fields.
            trace_header_fields: List of custom trace header fields.
            trace_data_spec: New trace data specification.

        Returns:
            A modified SEG-D spec with custom standard.
        """
        new_spec = self.model_copy(deep=True)
        new_spec.segd_standard = SegdStandard.CUSTOM

        if binary_header_fields is not None:
            new_spec.binary_header.customize(binary_header_fields)

        if trace_header_fields is not None:
            new_spec.trace.header.customize(trace_header_fields)

        if trace_data_spec is not None:
            new_spec.trace.data = trace_data_spec

        return new_spec


class SegdInfo(CamelCaseModel):
    """Concise and useful information about SEG-D files / catalogs."""

    uri: str = Field(..., description="URI of the first SEG-D file.")
    segd_standard: SegdStandard | None = Field(
        ..., description="SEG-D format profile. Can also be custom."
    )
    num_traces: int = Field(..., description="Number of traces across all records.")
    samples_per_trace: int = Field(..., description="Samples per trace.")
    sample_interval: int | float = Field(..., description="Sample interval in µs.")
    file_size: int = Field(..., description="Total size in bytes of all files.")
    num_records: int = Field(..., description="Number of RAW records.")
