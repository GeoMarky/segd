# Ingest to MDIO

Optional extra that converts demultiplexed SEG-D `8058` RAW records plus UKOOA
P1/90 navigation into an [MDIO](https://mdio.dev) / Zarr dataset. Core `segd`
stays on Python `>=3.11`; the MDIO extra requires Python `>=3.12`.

## Install

```bash
uv pip install -e ".[mdio]"
# or
uv sync --extra mdio
```

## API

```python
from mdio.builder.template_registry import get_template
from segd.mdio import segd_to_mdio

segd_to_mdio(
    mdio_template=get_template("StreamerShotGathers3D"),
    raw_urls=["/path/R1.RAW", "/path/R2.RAW"],  # list, single file, or directory
    p190_path="/path/line.P190",
    output_path="/path/out.mdio",
    overwrite=False,
    grid_overrides={"auto_shot_wrap": False},  # or mdio.segy.geometry.GridOverrides
    dim_defaults={"cable": 1, "gun": 1},  # optional sail_line_map
    file_prefix="R",  # directory scan defaults
    file_suffix="RAW",
    # file_list="/path/shots.txt",             # optional one-name-per-line list
)
```

Directory scans use `{file_prefix}*.{file_suffix}` (default `R*.RAW`). Pass an
explicit sequence of paths, or a `file_list` text file (relative names resolve
against a directory `raw_urls`).

CLI:

```bash
# Explicit file list
segd mdio import R037943.RAW R037944.RAW \
  --p190 Seq014.P190 \
  -o /tmp/out.mdio \
  --template StreamerShotGathers3D \
  --overwrite

# Directory scan with custom naming
segd mdio import /data/reel \
  --prefix SHOT --suffix sgd \
  --p190 Seq014.P190 -o /tmp/out.mdio

# Filename list (relative to directory)
segd mdio import /data/reel --file-list shots.txt \
  --p190 Seq014.P190 -o /tmp/out.mdio
```

## Architecture (P190 first)

1. Open P190 (shot table + receivers).
2. Build a light RAW catalog (general-header probes only).
3. Join each record to a P190 shot by `shot_point` (day-of-year checked when both present).
4. Synthesize logical index headers in 10 000-trace blocks from catalog + P190
   (no full-sample load in the parent process).
5. Reuse MDIO `GridOverrides` → `IndexStrategyRegistry` → `SchemaResolver` → `Grid`.
6. Write an empty MDIO Zarr skeleton, then process-pool blocked sample I/O via
   `SegdFile` in each worker.

## Template field mapping

Logical SEG-D headers (see `segd.standards.fields.trace.Demux8058`) include MDIO
dimension / coordinate names:

| Field | Source |
|-------|--------|
| `shot_point` | GH3 shot point |
| `channel` | 1…N within the record |
| `cable` / `gun` | defaults (`1`) or `dim_defaults` |
| `sail_line` | dense id from unique P190 `line_name` (override with `sail_line_map`) |
| `source_coord_*` / `group_coord_*` | P190 metres × `coordinate_scalar=-10` |
| `orig_field_record_num` | FFID / extended file number |

Streamer **field** templates (`StreamerFieldRecords3D`) still need
`auto_shot_wrap=True` so MDIO can emit `shot_index`. Shot-gather templates can
use dense `shot_point` directly.

## Grid overrides

Do not reimplement. Pass MDIO’s `GridOverrides` (or a dict with the same keys /
aliases). Validation is MDIO’s `validate_overrides_for_template`.

## Scale notes

- Never load all RAW sample volumes in the parent process.
- Index path prefers P190 + catalog GH metadata; demux sample I/O only inside
  workers for live grid cells.
- Header synthesis block size defaults to **10 000** (same as MDIO `parse_headers`).
- Workers: one `SegdFile` open per process; fetch only requested global indices.
- Catalog build is O(n_records) header probes — fine for reel-scale file counts;
  millions of tiny files may need a future sidecar index.

## File-header attrs

MDIO stores a `segd_file_header` scalar variable with attrs:

- `textHeader` — external-header / summary text
- `binaryHeader` — logical binary header dict
- `p190Path` — navigation path used for the ingest
- `rawUrls` — ordered RAW URL list

This is **not** a 400-byte SEG-Y binary header.

## Open / reader contract (SegdFile)

`SegdFile` remains the MDIO-shaped reader surface:

```python
SegdFile(
    url: str | Sequence[str],
    spec: SegdSpec | None = None,
    settings: SegdFileSettings | None = None,
    header_overrides: SegdHeaderOverrides | None = None,
    navigation: str | None = None,  # P190
    cable: int = 1,
    gun: int = 1,
    sail_line_map: dict[str, int] | None = None,
)
```

`spec.trace.header.itemsize` is the **physical** demux trace-header length
(e.g. 248), not 240. Logical headers from `header[i]` are authoritative across a
multi-file RAW list.
