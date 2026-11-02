"""Pre-built SEG-D specs."""

from __future__ import annotations

from segd.schema.base import Endianness
from segd.schema.format import ScalarType
from segd.schema.header import HeaderSpec
from segd.schema.segd import SegdSpec
from segd.schema.segd import SegdStandard
from segd.schema.trace import TraceDataSpec
from segd.schema.trace import TraceSpec
from segd.standards.fields import binary as binary_fields
from segd.standards.fields import trace as trace_fields

# Default physical demux header size observed for CASIE21 8058 records.
DEFAULT_DEMUX_TRACE_HEADER_SIZE = 248


def _demux_8058_spec() -> SegdSpec:
    """Build the demultiplexed IEEE-32 (8058) logical spec."""
    binary_header = HeaderSpec(
        fields=[field.model for field in binary_fields.Demux8058],
        item_size=32,
        offset=0,
    )
    trace_header = HeaderSpec(
        fields=[field.model for field in trace_fields.Demux8058],
        item_size=DEFAULT_DEMUX_TRACE_HEADER_SIZE,
    )
    trace = TraceSpec(
        header=trace_header,
        data=TraceDataSpec(format=ScalarType.FLOAT32, samples=None, interval=None),
        offset=None,
    )
    return SegdSpec(
        segd_standard=SegdStandard.DEMUX_8058,
        binary_header=binary_header,
        trace=trace,
        endianness=Endianness.BIG,
    )
