"""Process-pool blocked Zarr writers that fetch samples via :class:`~segd.file.SegdFile`."""

from __future__ import annotations

import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from typing import TYPE_CHECKING

import numpy as np
import zarr
from mdio.api.io import _normalize_storage_options
from mdio.builder.schemas.v1.stats import CenteredBinHistogram
from mdio.builder.schemas.v1.stats import SummaryStatistics
from mdio.constants import ZarrFormat
from mdio.constants import fill_value_map
from mdio.core.config import MDIOSettings
from mdio.core.indexing import ChunkIterator
from tqdm.auto import tqdm
from zarr import open_group as zarr_open_group
from zarr.core.config import config as zarr_config

from segd.file import SegdFile

if TYPE_CHECKING:
    from upath import UPath
    from xarray import Dataset as xr_Dataset
    from zarr import Array as zarr_Array

    from segd.mdio.file_info import SegdFileArguments

logger = logging.getLogger(__name__)

_worker_state: dict[str, object] = {}


def _create_stats() -> SummaryStatistics:
    histogram = CenteredBinHistogram(bin_centers=[], counts=[])
    return SummaryStatistics(
        count=0, min=0, max=0, sum=0, sum_squares=0, histogram=histogram
    )


def _update_stats(
    final_stats: SummaryStatistics, partial_stats: SummaryStatistics
) -> None:
    final_stats.count += partial_stats.count
    final_stats.min = min(final_stats.min, partial_stats.min)
    final_stats.max = max(final_stats.max, partial_stats.max)
    final_stats.sum += partial_stats.sum
    final_stats.sum_squares += partial_stats.sum_squares


def trace_worker_init(  # noqa: PLR0913
    segd_file_kwargs: SegdFileArguments,
    output_path: str,
    storage_options: dict[str, object] | None,
    use_consolidated: bool,
    data_variable_name: str,
    grid_map: zarr_Array,
) -> None:
    """Initialize per-process state for SEG-D → Zarr ingestion workers."""
    zarr_config.set({"threading.max_workers": 1})

    zarr_group = zarr_open_group(
        output_path,
        mode="r+",
        storage_options=storage_options,
        use_consolidated=use_consolidated,
    )

    _worker_state["segd_file"] = SegdFile(
        url=segd_file_kwargs["url"],
        spec=segd_file_kwargs.get("spec"),
        settings=segd_file_kwargs.get("settings"),
        header_overrides=segd_file_kwargs.get("header_overrides"),
        navigation=segd_file_kwargs.get("navigation"),
        cable=segd_file_kwargs.get("cable", 1),
        gun=segd_file_kwargs.get("gun", 1),
        sail_line_map=segd_file_kwargs.get("sail_line_map"),
    )
    _worker_state["data_array"] = zarr_group[data_variable_name]
    _worker_state["header_array"] = zarr_group.get("headers")
    _worker_state["grid_map"] = grid_map


def trace_worker(region: dict[str, slice]) -> SummaryStatistics | None:
    """Write one chunk region of samples (and headers) into the MDIO Zarr store."""
    segd_file: SegdFile = _worker_state["segd_file"]  # type: ignore[assignment]
    data_array: zarr_Array = _worker_state["data_array"]
    header_array: zarr_Array | None = _worker_state["header_array"]
    grid_map: zarr_Array = _worker_state["grid_map"]

    region_slices = tuple(region.values())
    local_grid_map = grid_map[region_slices[:-1]]

    not_null = local_grid_map != fill_value_map.get(local_grid_map.dtype.name)
    if not not_null.any():
        return None

    live_trace_indexes = local_grid_map[not_null].tolist()
    indices = np.asarray(live_trace_indexes, dtype=np.int64)

    samples = np.asarray(segd_file.sample.fetch(indices))
    if samples.ndim == 1:
        samples = samples.reshape(1, -1)

    header_region_slices = region_slices[:-1]
    full_shape = tuple(s.stop - s.start for s in region_slices)
    header_shape = tuple(s.stop - s.start for s in header_region_slices)

    if header_array is not None:
        headers = np.asarray(segd_file.header[indices])
        if headers.ndim == 0:
            headers = headers.reshape(1)
        # Project onto the headers Zarr dtype (field intersection, packed).
        target_dtype = header_array.dtype
        projected = np.empty(len(headers), dtype=target_dtype)
        for name in target_dtype.names or ():
            if name in (headers.dtype.names or ()):
                projected[name] = headers[name]
            else:
                projected[name] = 0
        tmp_headers = np.full(header_shape, header_array.fill_value, dtype=target_dtype)
        tmp_headers[not_null] = projected
        header_array[header_region_slices] = tmp_headers

    tmp_samples = np.full(full_shape, data_array.fill_value, dtype=data_array.dtype)
    tmp_samples[not_null] = samples
    data_array[region_slices] = tmp_samples

    nonzero_samples = np.ma.masked_values(samples, 0, copy=False)
    nonzero_count = nonzero_samples.count()
    if nonzero_count == 0:
        return None

    histogram = CenteredBinHistogram(bin_centers=[], counts=[])
    return SummaryStatistics(
        count=int(nonzero_count),
        min=float(nonzero_samples.min()),
        max=float(nonzero_samples.max()),
        sum=float(nonzero_samples.sum(dtype="float64")),
        sum_squares=float(np.ma.power(nonzero_samples, 2).sum(dtype="float64")),
        histogram=histogram,
    )


def to_zarr(  # noqa: PLR0913
    segd_file_kwargs: SegdFileArguments,
    output_path: UPath,
    grid_map: zarr_Array,
    dataset: xr_Dataset,
    data_variable_name: str,
) -> SummaryStatistics:
    """Blocked I/O from SEG-D to chunked ``xarray.Dataset`` / Zarr."""
    settings = MDIOSettings()
    data = dataset[data_variable_name]
    final_stats = _create_stats()

    data_variable_chunks = data.encoding.get("chunks")
    worker_chunks = data_variable_chunks[:-1] + (data.shape[-1],)
    chunk_iter = ChunkIterator(
        shape=data.shape, chunks=worker_chunks, dim_names=data.dims
    )
    num_chunks = chunk_iter.num_chunks

    zarr_format = zarr.config.get("default_zarr_format")
    use_consolidated = zarr_format == ZarrFormat.V2

    storage_options = _normalize_storage_options(output_path)
    zarr_group = zarr_open_group(
        output_path.as_posix(),
        mode="r+",
        storage_options=storage_options,
        use_consolidated=use_consolidated,
    )

    num_workers = min(num_chunks, settings.import_cpus)
    context = mp.get_context("spawn")

    executor = ProcessPoolExecutor(
        max_workers=num_workers,
        mp_context=context,
        initializer=trace_worker_init,
        initargs=(
            segd_file_kwargs,
            output_path.as_posix(),
            storage_options,
            use_consolidated,
            data_variable_name,
            grid_map,
        ),
    )

    with executor:
        futures = [executor.submit(trace_worker, region) for region in chunk_iter]
        iterable = tqdm(
            as_completed(futures),
            total=num_chunks,
            unit="block",
            desc="Ingesting SEG-D traces",
        )
        for future in iterable:
            result = future.result()
            if result is not None:
                _update_stats(final_stats, result)

    attr_json = final_stats.model_dump_json()
    zarr_group[data_variable_name].attrs.update({"statsV1": attr_json})

    if zarr.config.get("default_zarr_format") == ZarrFormat.V2:
        zarr.consolidate_metadata(zarr_group.store)

    return final_stats
