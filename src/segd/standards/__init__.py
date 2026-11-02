"""SEG-D standards registry."""

from segd.schema.segd import SegdStandard
from segd.standards.registry import get_segd_standard
from segd.standards.registry import register_segd_standard
from segd.standards.spec import DEFAULT_DEMUX_TRACE_HEADER_SIZE
from segd.standards.spec import _demux_8058_spec

register_segd_standard(SegdStandard.DEMUX_8058, _demux_8058_spec())

__all__ = [
    "DEFAULT_DEMUX_TRACE_HEADER_SIZE",
    "get_segd_standard",
    "register_segd_standard",
]
