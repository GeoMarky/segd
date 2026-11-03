# segd

Python SEG-D and UKOOA P1/90 I/O with schemas, cloud support via fsspec, and an API
shaped like [segy](https://github.com/TGSAI/segy).

> 🚧👷 This project is under active development. Expect potential changes to the API
> as we process more datasets. 👷🚧

## Features

- Read demultiplexed SEG-D format `8058` (32-bit IEEE) records
- Open a single `.RAW` file or an ordered **list** of RAW files as one logical trace set
- Read and write UKOOA P1/90 (P190) navigation and join it onto trace headers
- Expose MDIO-compatible trace header field names (`source_coord_x`, `group_coord_y`, …)
- Optional export to [MDIO](https://mdio.dev) / [multidimio](https://github.com/TGSAI/mdio-python) and [SEG-Y](https://github.com/TGSAI/segy)
- Spec-driven schemas, factory-based writes, Typer CLI, and Sphinx docs

## Quickstart

```python
from segd import SegdFile

# One shot
sf = SegdFile("/path/to/R037943_1623938836.RAW")
print(sf.num_traces, sf.samples_per_trace)

# Many shots as one logical file, with P190 geometry
sf = SegdFile(
    [
        "/path/to/R037943_1623938836.RAW",
        "/path/to/R037944_1623938853.RAW",
    ],
    navigation="/path/to/line.P190",
)
trace = sf.trace[0]
print(trace.header["energy_source_point_num"], trace.header["source_coord_x"])
```

```python
from segd.p190 import P190File

nav = P190File("/path/to/line.P190")
print(len(nav.shots), nav.receivers.shape)
```

## Installation

```bash
uv add segd
# or
pip install segd
```

Optional MDIO ingest (Python `>=3.12`):

```bash
uv pip install -e ".[mdio]"
# or
uv sync --extra mdio
```

```python
from mdio.builder.template_registry import get_template
from segd.mdio import segd_to_mdio

segd_to_mdio(
    get_template("StreamerShotGathers3D"),
    raw_urls=["shot1.RAW", "shot2.RAW"],
    p190_path="line.P190",
    output_path="out.mdio",
)
```

See [docs/mdio_contract.md](docs/mdio_contract.md) for grid overrides, field mapping, and scale notes.

Optional SEG-Y export:

```bash
uv pip install -e ".[segy]"
# or
uv sync --extra segy
```

```python
from segd.segy import segd_to_segy

segd_to_segy(
    raw_urls=["shot1.RAW", "shot2.RAW"],
    output_path="out.segy",
    p190_path="line.P190",  # optional
    sample_format="ieee",   # default; or "ibm"
)
```

See [docs/segy_export.md](docs/segy_export.md) for details.

## Development

```bash
uv sync
uv run pytest
uv run nox
```

## License

Apache-2.0

## Credits

Created by [SeismoForge AI](https://seismoforge.ai) and developed by
[Mark Roberts](https://github.com/GeoMarky).

This package is heavily inspired by the [segy](https://github.com/TGSAI/segy)
package. The CI/CD tooling is loosely based on
[Hypermodern Python Cookiecutter](https://github.com/cjolowicz/cookiecutter-hypermodern-python)
with more modern tooling applied elsewhere.
