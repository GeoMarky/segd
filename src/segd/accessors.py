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


def _scale_coord(value: float, scalar: int = int(COORD_SCALAR)) -> int:
    """Scale a metre coordinate into an int32 SEG-Y-style field."""
    if scalar == 0:
        return int(round(value))
    if scalar > 0:
        return int(round(value / scalar))
    return int(round(value * abs(scalar)))


class TraceAccessor:
    """Build decode pipelines and logical headers for SEG-D traces."""

    def __init__(
        self,
        trace_spec: TraceSpec,
        header_overrides: SegdHeaderOverrides | None = None,
    ) -> None:
        self.trace_spec = trace_spec
        self.header_overrides = header_overrides
        self.header_decode_pipeline = TransformPipeline()
        self.sample_decode_pipeline = TransformPipeline()
        self.trace_decode_pipeline = TransformPipeline()

    def build_logical_headers(  # noqa: PLR0915
        self,
        indices: NDArray[Any],
        catalog: RecordCatalog,
        navigation: P190File | None = None,
    ) -> HeaderArray:
        """Construct logical MDIO-compatible headers for global indices."""
        dtype = self.trace_spec.header.dtype
        headers = np.zeros(len(indices), dtype=dtype)

        shot_map: dict[int, Any] = {}
        if navigation is not None:
            for gather in navigation.shot_gathers:
                shot_map[gather.shot_point] = gather

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

            if self.header_overrides is not None:
                names = dtype.names or ()
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
