# MDIO reader contract

This package is designed so a future MDIO SEG-D ingest path can mirror the existing
SEG-Y path that uses `segy.SegyFile`. **MDIO itself is not modified by this package.**

## Open arguments

```python
SegdFile(
    url: str | Sequence[str],
    spec: SegdSpec | None = None,
    settings: SegdFileSettings | None = None,
    header_overrides: SegdHeaderOverrides | None = None,
    navigation: str | None = None,  # P190
)
```

`url` may be a list of RAW files. Trace order follows the list (or `settings.order`).
`SegdFile.url` is the first file (MDIO wrappers that pass `.url` keep working);
`SegdFile.urls` is the full list.

## File metadata (mirror `SegyFileInfo`)

| Attribute | Notes |
|-----------|--------|
| `num_traces` | Sum of channels across all RAW records |
| `sample_labels` | `int32` microseconds (`0, dt, 2*dt, …`) |
| `text_header` | External-header ASCII summary |
| `binary_header.to_dict()` | Includes `sample_interval`, `samples_per_trace`, `measurement_system_code` |
| `fs` | fsspec filesystem for the first URL |

## Trace headers

Logical names match SEG-Y Rev0 / MDIO expectations, including:

- `orig_field_record_num` (FFID)
- `trace_num_orig_record` (channel)
- `energy_source_point_num` (shot point)
- `source_coord_x/y`, `group_coord_x/y`, `coordinate_scalar`
- `samples_per_trace`, `sample_interval`
- time fields: `year_recorded`, `day_of_year`, `hour_of_day`, …

With P190 navigation, coordinates are stored as `int32` with `coordinate_scalar = -10`
(0.1 m). Without P190, coordinate fields remain zero unless overridden.

## Indexing API

```python
sf.header[i]   # HeaderArray
sf.sample[i]   # ndarray (n_samples,) or (n, n_samples)
sf.trace[i]    # TraceArray with .header and .sample
sf.trace.fetch(indices, raw=True)  # physical demux records
```

## Spec surface used by MDIO

- `spec.trace.header.fields` / `.dtype` / `.itemsize`
- `spec.trace.dtype`
- `spec.binary_header.offset` / `.itemsize` / `.names` / `.dtype`
- `accessors.trace_decode_pipeline`

**Important:** `spec.trace.header.itemsize` is the **physical** demux trace-header
length (for example 248), not 240. A future MDIO SEG-D reader must use
`itemsize` from the spec and must treat per-trace logical headers as authoritative
across a multi-file RAW list. Do not assume a 240-byte SEG-Y trace header.

`header[i]` returns the **logical** named view (SEG-Y field names). Viewing
`trace.fetch(..., raw=True)` bytes as `spec.trace.dtype` does **not** map physical
SEG-D demux bytes onto those logical fields; use `header` / decoded `trace` instead.
