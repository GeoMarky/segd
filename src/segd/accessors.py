"""Decode pipelines and logical header construction."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import numpy as np

from segd.arrays import HeaderArray
from segd.arrays import TraceArray
from segd.exceptions import NavigationJoinError
from segd.transforms import TransformPipeline

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from segd.catalog import RecordCatalog
    from segd.config import SegdHeaderOverrides
    from segd.p190.file import P190File
    from segd.schema import TraceSpec


COORD_SCALAR = np.int16(-10)

# Default streamer geometry for single-cable / single-gun surveys.
DEFAULT_CABLE = 1
DEFAULT_GUN = 1


def _scale_coord(value: float, scalar: int = int(COORD_SCALAR)) -> int:
    """Scale a metre coordinate into an int32 SEG-Y-style field."""
    if scalar == 0:
        return int(round(value))
    if scalar > 0:
        return int(round(value / scalar))
    return int(round(value * abs(scalar)))


def build_sail_line_map(line_names: list[str]) -> dict[str, int]:
    """Map unique P190 line names to dense sail_line integers starting at 1."""
    unique: list[str] = []
    for name in line_names:
        if name not in unique:
            unique.append(name)
    return {name: i + 1 for i, name in enumerate(unique)}


class TraceAccessor:
    """Build decode pipelines and logical headers for SEG-D traces."""

    def __init__(
        self,
        trace_spec: TraceSpec,
        header_overrides: SegdHeaderOverrides | None = None,
        *,
        cable: int = DEFAULT_CABLE,
        gun: int = DEFAULT_GUN,
        sail_line_map: dict[str, int] | None = None,
    ) -> None:
        self.trace_spec = trace_spec
        self.header_overrides = header_overrides
        self.cable = cable
        self.gun = gun
        self.sail_line_map = sail_line_map or {}
        self.header_decode_pipeline = TransformPipeline()
        self.sample_decode_pipeline = TransformPipeline()
        self.trace_decode_pipeline = TransformPipeline()

    def build_logical_headers(  # noqa: PLR0912, PLR0915
        self,
        indices: NDArray[Any],
        catalog: RecordCatalog,
        navigation: P190File | None = None,
    ) -> HeaderArray:
        """Construct logical MDIO-compatible headers for global indices."""
        dtype = self.trace_spec.header.dtype
        headers = np.zeros(len(indices), dtype=dtype)
        names = set(dtype.names or ())

        shot_map: dict[int, Any] = {}
        sail_map = dict(self.sail_line_map)
        if navigation is not None:
            for gather in navigation.shot_gathers:
                shot_map[gather.shot_point] = gather
            if not sail_map:
                sail_map = build_sail_line_map(
                    [g.line_name for g in navigation.shot_gathers]
                )

        for i, global_index in enumerate(indices):
            record, local = catalog.locate(int(global_index))
            info = record.info
            channel = local + 1
            shot_point = info.shot_point or 0

            row = headers[i]
            row["trace_seq_num_line"] = int(global_index) + 1
            row["trace_seq_num_reel"] = int(global_index) + 1
            row["orig_field_record_num"] = info.file_number
            row["trace_num_orig_record"] = channel
            row["energy_source_point_num"] = shot_point
            row["ensemble_num"] = shot_point
            row["trace_num_ensemble"] = channel
            row["samples_per_trace"] = info.samples
            row["sample_interval"] = info.sample_interval_us
            row["year_recorded"] = info.year
            row["day_of_year"] = info.day_of_year
            row["hour_of_day"] = info.hour
            row["minute_of_hour"] = info.minute
            row["second_of_minute"] = info.second
            row["coordinate_unit"] = 1  # length units

            if "shot_point" in names:
                row["shot_point"] = shot_point
            if "channel" in names:
                row["channel"] = channel
            if "cable" in names:
                row["cable"] = self.cable
            if "gun" in names:
                row["gun"] = self.gun

            if navigation is not None:
                if shot_point not in shot_map:
                    msg = (
                        f"Shot point {shot_point} from record {record.url} "
                        "not found in P190 navigation."
                    )
                    raise NavigationJoinError(msg)
                gather = shot_map[shot_point]
                if len(gather.receivers) != info.channels:
                    msg = (
                        f"P190 shot {shot_point} has {len(gather.receivers)} receivers "
                        f"but SEG-D record has {info.channels} channels."
                    )
                    raise NavigationJoinError(msg)

                if "sail_line" in names:
                    row["sail_line"] = sail_map.get(gather.line_name, 1)

                src = gather.source
                recv = gather.receivers[local]
                row["coordinate_scalar"] = COORD_SCALAR
                row["elevation_depth_scalar"] = COORD_SCALAR
                row["source_coord_x"] = _scale_coord(src.easting)
                row["source_coord_y"] = _scale_coord(src.northing)
                row["group_coord_x"] = _scale_coord(recv.easting)
                row["group_coord_y"] = _scale_coord(recv.northing)
                row["source_water_depth"] = _scale_coord(src.water_depth)
                row["receiver_group_elevation"] = _scale_coord(recv.depth)
                dx = recv.easting - src.easting
                dy = recv.northing - src.northing
                row["source_to_receiver_distance"] = _scale_coord(
                    float(np.hypot(dx, dy))
                )
            elif "sail_line" in names:
                row["sail_line"] = 1

            if self.header_overrides is not None:
                for key, value in self.header_overrides.trace_header.items():
                    if key in names:
                        row[key] = value

        return HeaderArray(self.header_decode_pipeline.apply(headers))

    def build_traces(
        self,
        indices: NDArray[Any],
        samples: NDArray[Any],
        catalog: RecordCatalog,
        navigation: P190File | None = None,
    ) -> TraceArray:
        """Combine logical headers and samples into a TraceArray."""
        headers = self.build_logical_headers(indices, catalog, navigation)
        samples = self.sample_decode_pipeline.apply(np.asarray(samples))

        if samples.ndim == 1:
            samples = samples.reshape(1, -1)
        header_arr = np.atleast_1d(headers)

        out = np.empty(len(indices), dtype=self.trace_spec.dtype)
        out["header"] = header_arr
        out["data"] = samples
        return TraceArray(self.trace_decode_pipeline.apply(out))
