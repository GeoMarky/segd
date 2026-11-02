"""SEG-D schema package."""

from segd.schema.base import BaseDataType
from segd.schema.base import CamelCaseModel
from segd.schema.base import Endianness
from segd.schema.format import ScalarType
from segd.schema.header import HeaderField
from segd.schema.header import HeaderSpec
from segd.schema.segd import SegdInfo
from segd.schema.segd import SegdSpec
from segd.schema.segd import SegdStandard
from segd.schema.trace import TraceDataSpec
from segd.schema.trace import TraceSpec

__all__ = [
    "BaseDataType",
    "CamelCaseModel",
    "Endianness",
    "HeaderField",
    "HeaderSpec",
    "ScalarType",
    "SegdInfo",
    "SegdSpec",
    "SegdStandard",
    "TraceDataSpec",
    "TraceSpec",
]
