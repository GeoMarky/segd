"""Fixed-width UKOOA P1/90 card schemas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PointRecord:
    """Parsed V/E/A/S/Z/C/T point record."""

    record_type: str
    line_name: str
    point_number: int
    point_index: int
    latitude_raw: str
    longitude_raw: str
    easting: float
    northing: float
    water_depth: float
    day_of_year: int
    time_hhmmss: str
    time_ms: int
    raw: str


@dataclass(frozen=True)
class ReceiverGroup:
    """One receiver group from an R card."""

    group_number: int
    easting: float
    northing: float
    depth: float


@dataclass(frozen=True)
class ShotGather:
    """One shot's navigation: source point plus receiver groups."""

    line_name: str
    shot_point: int
    source: PointRecord
    vessel: PointRecord | None
    echo: PointRecord | None
    antennas: tuple[PointRecord, ...]
    tail: PointRecord | None
    gun: PointRecord | None
    receivers: tuple[ReceiverGroup, ...]
