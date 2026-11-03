"""SEG-D + P190 → MDIO ingestion pipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import numpy as np
from mdio.api.io import _normalize_path
from mdio.converters.exceptions import GridTraceCountError
from mdio.core.grid import Grid
from mdio.ingestion.dataset_factory import build_mdio_dataset
from mdio.ingestion.grid_qc import grid_density_qc
from mdio.ingestion.metadata import add_grid_override_to_metadata
from mdio.ingestion.schema.resolver import SchemaResolver
from mdio.ingestion.segy.coordinates import get_spatial_coordinate_unit
from mdio.ingestion.segy.coordinates import resolve_units
from mdio.ingestion.segy.index_strategies import IndexStrategyRegistry
from mdio.segy.geometry import GridOverrides
from mdio.segy.geometry import validate_overrides_for_template
from mdio.segy.utilities import build_mdio_header_type

from segd.catalog import build_catalog
from segd.catalog import resolve_raw_urls
from segd.config import SegdFileSettings
from segd.config import SegdHeaderOverrides
from segd.file import SegdFile
from segd.mdio.file_info import SegdFileArguments
from segd.mdio.file_info import get_segd_file_info
from segd.mdio.headers import read_index_headers
from segd.mdio.serializer import serialize_to_mdio
from segd.p190 import P190File

if TYPE_CHECKING:
    from collections.abc import Mapping
    from collections.abc import Sequence
    from pathlib import Path

    from mdio.builder.templates.base import AbstractDatasetTemplate
    from mdio.core.dimension import Dimension
    from mdio.ingestion.schema import ResolvedSchema
    from upath import UPath

    from segd.schema import SegdSpec

logger = logging.getLogger(__name__)


def _resolve_output_path(output_path: UPath | Path | str, overwrite: bool) -> UPath:
    """Normalize output path and verify overwrite policy."""
    output_path = _normalize_path(output_path)
    if not overwrite and output_path.exists():
        err = (
            f"Output location '{output_path.as_posix()}' exists. "
            "Set `overwrite=True` if intended."
        )
        raise FileExistsError(err)
    return output_path


def _verify_calculated_dimensions(
    schema: ResolvedSchema,
    dimensions: list[Dimension],
    template_name: str,
) -> None:
    """Verify all calculated dimensions required by the schema were produced."""
    missing = schema.missing_calculated_dimensions(dim.name for dim in dimensions)
    if missing:
        err = (
            f"Required computed fields {sorted(missing)} for template {template_name} not found "
            f"after grid overrides. Please ensure the correct grid overrides are applied."
        )
        raise ValueError(err)


def _build_grid(
    dimensions: list[Dimension], indexed_headers: np.ndarray, num_traces: int
) -> Grid:
    """Build the ingestion grid, run density QC, and verify live trace count."""
    grid = Grid(dims=dimensions)
    grid_density_qc(grid, num_traces)
    grid.build_map(indexed_headers)

    live_trace_count = int(np.sum(grid.live_mask))
    if live_trace_count != num_traces:
        for dim_name in grid.dim_names:
            logger.warning(
                "%s min: %s max: %s",
                dim_name,
                grid.get_min(dim_name),
                grid.get_max(dim_name),
            )
        logger.warning("Ingestion grid shape: %s.", grid.shape)
        raise GridTraceCountError(live_trace_count, num_traces)

    return grid


def _validate_spec_fields(
    segd_spec: SegdSpec, mdio_template: AbstractDatasetTemplate
) -> None:
    """Ensure the SEG-D logical header fields cover the template requirements."""
    header_fields = {field.name for field in segd_spec.trace.header.fields}
    required_fields = set(mdio_template.spatial_dimension_names) | set(
        mdio_template.coordinate_names
    )
    required_fields = required_fields - set(mdio_template.calculated_dimension_names)

    from mdio.segy.scalar import SCALE_COORDINATE_KEYS  # noqa: PLC0415

    if any(field in SCALE_COORDINATE_KEYS for field in required_fields):
        required_fields = required_fields | {"coordinate_scalar"}
    missing_fields = required_fields - header_fields
    if missing_fields:
        err = (
            f"Required fields {sorted(missing_fields)} for template {mdio_template.name} "
            f"not found in the provided segd_spec"
        )
        raise ValueError(err)


def _parse_grid_overrides(
    grid_overrides: GridOverrides | Mapping[str, Any] | None,
) -> GridOverrides | None:
    if grid_overrides is None:
        return None
    if isinstance(grid_overrides, GridOverrides):
        return grid_overrides
    return GridOverrides.model_validate(dict(grid_overrides))


def _parse_dim_defaults(
    dim_defaults: Mapping[str, Any] | None,
) -> tuple[int, int, dict[str, int] | None]:
    """Extract cable / gun / sail_line_map from optional dim_defaults."""
    if not dim_defaults:
        return 1, 1, None
    cable = int(dim_defaults.get("cable", 1))
    gun = int(dim_defaults.get("gun", 1))
    sail_line_map = dim_defaults.get("sail_line_map")
    if sail_line_map is not None:
        sail_line_map = {str(k): int(v) for k, v in dict(sail_line_map).items()}
    return cable, gun, sail_line_map


def segd_to_mdio(  # noqa: PLR0913
    mdio_template: AbstractDatasetTemplate,
    raw_urls: str | Path | Sequence[str | Path] | None,
    p190_path: str | Path,
    output_path: str | Path,
    *,
    file_list: str | Path | None = None,
    file_prefix: str = "R",
    file_suffix: str = "RAW",
    file_pattern: str | None = None,
    segd_spec: SegdSpec | None = None,
    overwrite: bool = False,
    grid_overrides: GridOverrides | Mapping[str, Any] | None = None,
    header_overrides: SegdHeaderOverrides | Mapping[str, Any] | None = None,
    settings: SegdFileSettings | None = None,
    dim_defaults: Mapping[str, Any] | None = None,
) -> None:
    """Convert SEG-D RAW records + P190 navigation into an MDIO dataset.

    Index headers are synthesized primarily from P190 geometry and catalog general
    headers (no full-sample load). Sample data is written via a process-pool blocked
    Zarr path that opens :class:`~segd.file.SegdFile` in each worker.

    ``FileExistsError`` is raised when the output exists and ``overwrite`` is false.
    ``ValueError`` is raised when required template fields or calculated dimensions
    are missing. ``GridTraceCountError`` is raised when live grid cells do not match
    the RAW trace count.

    Args:
        mdio_template: MDIO dataset template (e.g. ``get_template("StreamerShotGathers3D")``).
        raw_urls: Single RAW URL, sequence of RAW URLs/filenames, or a directory to scan.
            May be ``None`` when ``file_list`` supplies the inputs.
        p190_path: Required UKOOA P1/90 navigation path.
        output_path: Output MDIO / Zarr path.
        file_list: Optional text file listing SEG-D filenames/paths (one per line).
            Relative names resolve against ``raw_urls`` when it is a directory.
        file_prefix: Directory-scan filename prefix (default ``R``).
        file_suffix: Directory-scan filename suffix / extension (default ``RAW``).
        file_pattern: Optional explicit glob overriding ``file_prefix`` / ``file_suffix``.
        segd_spec: Optional SEG-D specification (inferred from the first record when omitted).
        overwrite: Whether to overwrite an existing output directory.
        grid_overrides: MDIO :class:`~mdio.segy.geometry.GridOverrides` or dict.
        header_overrides: Optional fixed logical header values.
        settings: :class:`~segd.config.SegdFileSettings` (endianness, storage, order).
        dim_defaults: Optional ``{"cable": 1, "gun": 1, "sail_line_map": {...}}``.
    """
    grid_overrides = _parse_grid_overrides(grid_overrides)
    validate_overrides_for_template(grid_overrides, mdio_template)

    settings = settings or SegdFileSettings()
    if header_overrides is not None and not isinstance(
        header_overrides, SegdHeaderOverrides
    ):
        header_overrides = SegdHeaderOverrides.model_validate(dict(header_overrides))

    cable, gun, sail_line_map = _parse_dim_defaults(dim_defaults)
    urls = resolve_raw_urls(
        raw_urls,
        file_list=file_list,
        prefix=file_prefix,
        suffix=file_suffix,
        pattern=file_pattern,
    )
    p190_path_str = str(p190_path)
    output_path = _resolve_output_path(output_path, overwrite)

    # Infer / validate spec against the template before heavy work.
    probe = SegdFile(
        urls[0],
        spec=segd_spec,
        settings=settings,
        header_overrides=header_overrides,
        cable=cable,
        gun=gun,
        sail_line_map=sail_line_map,
    )
    resolved_spec = probe.spec
    _validate_spec_fields(resolved_spec, mdio_template)

    segd_file_kwargs: SegdFileArguments = {
        "url": urls,
        "spec": resolved_spec,
        "settings": settings,
        "header_overrides": header_overrides,
        "navigation": p190_path_str,
        "cable": cable,
        "gun": gun,
        "sail_line_map": sail_line_map,
    }
    file_info = get_segd_file_info(segd_file_kwargs)

    # SegdFileInfo matches the SegyFileInfo attributes this helper reads.
    spatial_unit = get_spatial_coordinate_unit(cast("Any", file_info))
    units = resolve_units(mdio_template, spatial_unit)

    schema_effect = IndexStrategyRegistry().schema_effect(grid_overrides)
    schema = SchemaResolver().resolve(mdio_template, schema_effect)

    catalog = build_catalog(
        urls,
        storage_options=settings.storage_options,
        order=settings.order,
    )
    navigation = P190File(
        p190_path_str,
        settings={"storage_options": settings.storage_options},
    )

    indexed_headers, dimensions = read_index_headers(
        catalog=catalog,
        navigation=navigation,
        trace_spec=resolved_spec.trace,
        file_info=file_info,
        schema=schema,
        grid_overrides=grid_overrides,
        synthesize_dims=mdio_template.synthesize_missing_dims,
        template=mdio_template,
        header_overrides=header_overrides,
        cable=cable,
        gun=gun,
        sail_line_map=sail_line_map,
    )
    _verify_calculated_dimensions(schema, dimensions, mdio_template.name)

    grid = _build_grid(dimensions, indexed_headers, file_info.num_traces)

    # SegdSpec exposes the trace-header layout this helper reads.
    header_dtype = build_mdio_header_type(cast("Any", resolved_spec))
    mdio_ds = build_mdio_dataset(
        schema=schema,
        sizes=grid.shape,
        header_dtype=header_dtype,
        units=units,
    )
    add_grid_override_to_metadata(dataset=mdio_ds, grid_overrides=grid_overrides)

    serialize_to_mdio(
        mdio_ds=mdio_ds,
        grid=grid,
        indexed_headers=indexed_headers,
        schema=schema,
        file_info=file_info,
        segd_file_kwargs=segd_file_kwargs,
        output_path=output_path,
    )


__all__ = ["segd_to_mdio"]
