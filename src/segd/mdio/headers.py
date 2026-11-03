"""P190-first blocked synthesis of MDIO index headers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

import numpy as np
from mdio.core.dimension import Dimension
from mdio.ingestion.segy.index_strategies import IndexStrategyRegistry
from mdio.segy.scalar import SCALE_COORDINATE_KEYS

from segd.accessors import COORD_SCALAR
from segd.accessors import DEFAULT_CABLE
from segd.accessors import DEFAULT_GUN
from segd.accessors import _scale_coord
from segd.accessors import build_sail_line_map
from segd.arrays import HeaderArray
from segd.mdio.join import join_catalog_to_p190

if TYPE_CHECKING:
    from mdio.builder.templates.base import AbstractDatasetTemplate
    from mdio.ingestion.schema import ResolvedSchema
    from mdio.segy.geometry import GridOverrides

    from segd.catalog import RecordCatalog
    from segd.config import SegdHeaderOverrides
    from segd.mdio.file_info import SegdFileInfo
    from segd.p190.file import P190File
    from segd.schema import TraceSpec

logger = logging.getLogger(__name__)

DEFAULT_HEADER_BLOCK_SIZE = 10_000


def _scale_array(
    values: np.ndarray[Any, Any], scalar: int = int(COORD_SCALAR)
) -> np.ndarray[Any, Any]:
    """Vectorized metre → int32 SEG-Y-style coordinate scaling."""
    if scalar == 0:
        return np.rint(values).astype(np.int32)
    if scalar > 0:
        return np.rint(values / scalar).astype(np.int32)
    return np.rint(values * abs(scalar)).astype(np.int32)


def synthesize_index_headers(  # noqa: PLR0912, PLR0913, PLR0915
    *,
    catalog: RecordCatalog,
    navigation: P190File,
    trace_spec: TraceSpec,
    subset: tuple[str, ...],
    header_overrides: SegdHeaderOverrides | None = None,
    cable: int = DEFAULT_CABLE,
    gun: int = DEFAULT_GUN,
    sail_line_map: dict[str, int] | None = None,
    block_size: int = DEFAULT_HEADER_BLOCK_SIZE,  # kept for API compat; unused
) -> HeaderArray:
    """Build logical index headers from the catalog + P190 (no sample I/O).

    Fills one record (shot) at a time with vectorized channel/receiver fields so
    reel-scale surveys stay practical in memory and time.
    """
    del block_size  # API compatibility with earlier blocked path
    record_to_p190 = join_catalog_to_p190(catalog, navigation)

    sail_map = sail_line_map or build_sail_line_map(
        [g.line_name for g in navigation.shot_gathers]
    )

    dtype = trace_spec.header.dtype
    names = set(dtype.names or ())
    num_traces = catalog.num_traces
    headers = np.zeros(num_traces, dtype=dtype)

    global_index = np.arange(num_traces, dtype=np.int64)
    if "trace_seq_num_line" in names:
        headers["trace_seq_num_line"] = global_index + 1
    if "trace_seq_num_reel" in names:
        headers["trace_seq_num_reel"] = global_index + 1
    if "coordinate_unit" in names:
        headers["coordinate_unit"] = 1
    if "cable" in names:
        headers["cable"] = cable
    if "gun" in names:
        headers["gun"] = gun
    if "coordinate_scalar" in names:
        headers["coordinate_scalar"] = COORD_SCALAR
    if "elevation_depth_scalar" in names:
        headers["elevation_depth_scalar"] = COORD_SCALAR

    for record_index, record in enumerate(catalog.records):
        info = record.info
        n_chan = info.channels
        start = record.global_trace_start
        stop = start + n_chan
        sl = slice(start, stop)
        channels = np.arange(1, n_chan + 1, dtype=np.int32)
        shot_point = int(info.shot_point or 0)

        if "orig_field_record_num" in names:
            headers["orig_field_record_num"][sl] = info.file_number
        if "trace_num_orig_record" in names:
            headers["trace_num_orig_record"][sl] = channels
        if "energy_source_point_num" in names:
            headers["energy_source_point_num"][sl] = shot_point
        if "ensemble_num" in names:
            headers["ensemble_num"][sl] = shot_point
        if "trace_num_ensemble" in names:
            headers["trace_num_ensemble"][sl] = channels
        if "samples_per_trace" in names:
            headers["samples_per_trace"][sl] = info.samples
        if "sample_interval" in names:
            headers["sample_interval"][sl] = info.sample_interval_us
        if "year_recorded" in names:
            headers["year_recorded"][sl] = info.year
        if "day_of_year" in names:
            headers["day_of_year"][sl] = info.day_of_year
        if "hour_of_day" in names:
            headers["hour_of_day"][sl] = info.hour
        if "minute_of_hour" in names:
            headers["minute_of_hour"][sl] = info.minute
        if "second_of_minute" in names:
            headers["second_of_minute"][sl] = info.second
        if "shot_point" in names:
            headers["shot_point"][sl] = shot_point
        if "channel" in names:
            headers["channel"][sl] = channels

        p190_index = record_to_p190[record_index]
        gather = navigation.shot_gathers[p190_index]
        if "sail_line" in names:
            headers["sail_line"][sl] = sail_map.get(gather.line_name, 1)

        src = gather.source
        src_x = _scale_coord(src.easting)
        src_y = _scale_coord(src.northing)
        if "source_coord_x" in names:
            headers["source_coord_x"][sl] = src_x
        if "source_coord_y" in names:
            headers["source_coord_y"][sl] = src_y
        if "source_water_depth" in names:
            headers["source_water_depth"][sl] = _scale_coord(src.water_depth)

        # Prefer tabular receivers when available (fast path).
        recv = navigation.receivers[p190_index]
        recv_x = _scale_array(recv[:, 0])
        recv_y = _scale_array(recv[:, 1])
        recv_z = _scale_array(recv[:, 2])
        if "group_coord_x" in names:
            headers["group_coord_x"][sl] = recv_x
        if "group_coord_y" in names:
            headers["group_coord_y"][sl] = recv_y
        if "receiver_group_elevation" in names:
            headers["receiver_group_elevation"][sl] = recv_z
        if "source_to_receiver_distance" in names:
            dist = np.hypot(recv[:, 0] - src.easting, recv[:, 1] - src.northing)
            headers["source_to_receiver_distance"][sl] = _scale_array(dist)

    if header_overrides is not None:
        for key, value in header_overrides.trace_header.items():
            if key in names:
                headers[key] = value

    if subset:
        headers = headers[list(subset)]

    return HeaderArray(headers)


def read_index_headers(  # noqa: PLR0913
    *,
    catalog: RecordCatalog,
    navigation: P190File,
    trace_spec: TraceSpec,
    file_info: SegdFileInfo,
    schema: ResolvedSchema,
    grid_overrides: GridOverrides | None,
    synthesize_dims: tuple[str, ...],
    template: AbstractDatasetTemplate | None = None,
    header_overrides: SegdHeaderOverrides | None = None,
    cable: int = 1,
    gun: int = 1,
    sail_line_map: dict[str, int] | None = None,
) -> tuple[np.ndarray[Any, Any], list[Dimension]]:
    """Synthesize headers, apply MDIO index strategies, and build dimensions."""
    required_fields = schema.required_fields()
    if any(field in SCALE_COORDINATE_KEYS for field in required_fields):
        required_fields = required_fields | {"coordinate_scalar"}

    spec_fields = {field.name for field in trace_spec.header.fields}
    subset = tuple(f for f in required_fields if f in spec_fields)

    logger.info(
        "Synthesizing %s index headers (%s fields) from P190 + catalog",
        catalog.num_traces,
        len(subset),
    )
    parsed_headers = synthesize_index_headers(
        catalog=catalog,
        navigation=navigation,
        trace_spec=trace_spec,
        subset=subset,
        header_overrides=header_overrides,
        cable=cable,
        gun=gun,
        sail_line_map=sail_line_map,
    )

    strategy = IndexStrategyRegistry().create_strategy(
        grid_overrides=grid_overrides,
        synthesize_dims=synthesize_dims,
        template=template,
    )
    logger.info("Using index strategy: %s", strategy.name)

    strategy.validate_headers(parsed_headers)
    indexed_headers = strategy.transform_headers(parsed_headers)

    dim_names = tuple(d.name for d in schema.dimensions if d.is_spatial)
    dimensions = strategy.compute_dimensions(indexed_headers, dim_names)

    sample_labels = file_info.sample_labels / 1000  # normalize µs → ms
    if all(sample_labels.astype("int64") == sample_labels):
        sample_labels = sample_labels.astype("int64")

    vertical_dim_name = schema.dimensions[-1].name
    dimensions.append(Dimension(coords=sample_labels, name=vertical_dim_name))

    return indexed_headers, dimensions
