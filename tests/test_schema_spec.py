"""SEG-D spec customization and trace dtype layout."""

from __future__ import annotations

import json

from segd.schema import Endianness
from segd.schema import HeaderField
from segd.schema import ScalarType
from segd.schema import SegdStandard
from segd.schema import TraceDataSpec
from segd.standards import get_segd_standard


def test_customize_replaces_header_fields_and_trace_data() -> None:
    spec = get_segd_standard(SegdStandard.DEMUX_8058)
    custom = spec.customize(
        binary_header_fields=[HeaderField(name="zz", format=ScalarType.INT16, byte=31)],
        trace_header_fields=[HeaderField(name="zz", format=ScalarType.INT16, byte=240)],
        trace_data_spec=TraceDataSpec(
            format=ScalarType.FLOAT32,
            samples=4,
            interval=1000,
        ),
    )
    assert custom.segd_standard is SegdStandard.CUSTOM
    assert custom.trace.data.samples == 4


def test_model_dump_uses_camel_case_aliases() -> None:
    spec = get_segd_standard(SegdStandard.DEMUX_8058)
    dumped = json.loads(spec.model_dump_json())
    assert "segdStandard" in dumped
    assert spec._repr_json_()["segdStandard"] == SegdStandard.DEMUX_8058.value


def test_endianness_symbol_and_native_trace_dtype() -> None:
    assert Endianness.BIG.symbol == ">"
    spec = get_segd_standard(SegdStandard.DEMUX_8058)
    assert spec.trace.header.itemsize > 0

    bare = spec.trace.model_copy(deep=True)
    bare.endianness = None
    bare.data.samples = 4
    assert bare.dtype.names == ("header", "data")
