"""Serialize a populated MDIO dataset and write SEG-D samples via blocked I/O."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

import numpy as np
from mdio.api.io import to_mdio
from mdio.builder.xarray_builder import to_xarray_dataset
from mdio.ingestion.segy.coordinates import populate_coordinates

from segd.mdio import blocked_io

if TYPE_CHECKING:
    from mdio.builder.schemas import Dataset
    from mdio.core.grid import Grid
    from mdio.ingestion.schema import ResolvedSchema
    from upath import UPath
    from xarray import Dataset as xr_Dataset

    from segd.mdio.file_info import SegdFileArguments
    from segd.mdio.file_info import SegdFileInfo

logger = logging.getLogger(__name__)


def add_segd_file_headers(
    xr_dataset: xr_Dataset, file_info: SegdFileInfo
) -> xr_Dataset:
    """Attach SEG-D / P190 summary attrs (not SEG-Y binary headers)."""
    xr_dataset["segd_file_header"] = ((), "")
    xr_dataset["segd_file_header"].attrs.update(
        {
            "textHeader": file_info.text_header,
            "binaryHeader": file_info.binary_header_dict,
            "p190Path": file_info.p190_path or "",
            "rawUrls": list(file_info.urls),
        }
    )
    return xr_dataset


def serialize_to_mdio(  # noqa: PLR0913
    mdio_ds: Dataset,
    grid: Grid,
    indexed_headers: np.ndarray[Any, Any],
    schema: ResolvedSchema,
    file_info: SegdFileInfo,
    segd_file_kwargs: SegdFileArguments,
    output_path: UPath,
) -> None:
    """Populate coordinates / mask and write SEG-D samples into MDIO Zarr."""
    non_dim_coords = {}
    for coord in schema.coordinates:
        if coord.name in indexed_headers.dtype.names:
            non_dim_coords[coord.name] = np.array(indexed_headers[coord.name])
        else:
            logger.warning(
                "Coordinate '%s' expected by schema but not found in transformed headers.",
                coord.name,
            )

    xr_dataset = to_xarray_dataset(mdio_ds=mdio_ds)

    xr_dataset, drop_vars_delayed = populate_coordinates(
        dataset=xr_dataset,
        grid=grid,
        coords=non_dim_coords,
        spatial_coordinate_scalar=file_info.coordinate_scalar,
    )

    xr_dataset = add_segd_file_headers(xr_dataset, file_info)
    xr_dataset.trace_mask.data[:] = grid.live_mask

    to_mdio(xr_dataset, output_path=output_path, mode="w", compute=False)

    unindexed_dims = [d for d in xr_dataset.dims if d not in xr_dataset.coords]
    for d in unindexed_dims:
        if d in drop_vars_delayed:
            drop_vars_delayed.remove(d)

    meta_ds = xr_dataset[drop_vars_delayed + ["trace_mask"]]
    to_mdio(meta_ds, output_path=output_path, mode="r+", compute=True)

    xr_dataset = xr_dataset.drop_vars(drop_vars_delayed)

    blocked_io.to_zarr(
        segd_file_kwargs=segd_file_kwargs,
        output_path=output_path,
        grid_map=grid.map,
        dataset=xr_dataset,
        data_variable_name=schema.default_variable_name,
    )
