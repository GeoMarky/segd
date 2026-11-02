"""Logical binary header field definitions (MDIO / SEG-Y compatible names)."""

from segd.standards.fields.base import SegStandardEnum


# fmt: off
class Demux8058(SegStandardEnum):
    """Logical binary header fields synthesized from SEG-D general headers."""

    SAMPLE_INTERVAL           = (1, "int32")
    SAMPLES_PER_TRACE         = (5, "int32")
    MEASUREMENT_SYSTEM_CODE   = (9, "int16")
    FORMAT_CODE               = (11, "int16")
    CHANNELS_PER_RECORD       = (13, "int32")
    FILE_NUMBER               = (17, "int32")
    YEAR_RECORDED             = (21, "int16")
    DAY_OF_YEAR               = (23, "int16")
    HOUR_OF_DAY               = (25, "int16")
    MINUTE_OF_HOUR            = (27, "int16")
    SECOND_OF_MINUTE          = (29, "int16")
# fmt: on
