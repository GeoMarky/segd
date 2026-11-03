"""Logical trace header field definitions (MDIO / SEG-Y compatible names)."""

from segd.standards.fields.base import SegStandardEnum


# fmt: off
class Demux8058(SegStandardEnum):
    """Logical demux trace header fields.

    Physical SEG-D demux headers are manufacturer-specific. These fields form a
    logical view populated from general headers, demux trace headers, and P190.
    """

    TRACE_SEQ_NUM_LINE          = (1, "int32")
    TRACE_SEQ_NUM_REEL          = (5, "int32")
    ORIG_FIELD_RECORD_NUM       = (9, "int32")
    TRACE_NUM_ORIG_RECORD       = (13, "int32")
    ENERGY_SOURCE_POINT_NUM     = (17, "int32")
    ENSEMBLE_NUM                = (21, "int32")
    TRACE_NUM_ENSEMBLE          = (25, "int32")
    SOURCE_TO_RECEIVER_DISTANCE = (37, "int32")
    RECEIVER_GROUP_ELEVATION    = (41, "int32")
    SOURCE_SURFACE_ELEVATION    = (45, "int32")
    SOURCE_WATER_DEPTH          = (61, "int32")
    RECEIVER_WATER_DEPTH        = (65, "int32")
    ELEVATION_DEPTH_SCALAR      = (69, "int16")
    COORDINATE_SCALAR           = (71, "int16")
    SOURCE_COORD_X              = (73, "int32")
    SOURCE_COORD_Y              = (77, "int32")
    GROUP_COORD_X               = (81, "int32")
    GROUP_COORD_Y               = (85, "int32")
    COORDINATE_UNIT             = (89, "int16")
    SAMPLES_PER_TRACE           = (115, "int16")
    SAMPLE_INTERVAL             = (117, "int16")
    YEAR_RECORDED               = (157, "int16")
    DAY_OF_YEAR                 = (159, "int16")
    HOUR_OF_DAY                 = (161, "int16")
    MINUTE_OF_HOUR              = (163, "int16")
    SECOND_OF_MINUTE            = (165, "int16")
    # MDIO template dimension / coordinate aliases (logical only)
    SHOT_POINT                  = (169, "int32")
    CHANNEL                     = (173, "int32")
    CABLE                       = (177, "int16")
    GUN                         = (179, "int16")
    SAIL_LINE                   = (181, "int32")
# fmt: on
