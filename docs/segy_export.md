# Export to SEG-Y

Optional extra that concatenates demultiplexed SEG-D `8058` RAW records into a
single SEG-Y file. Reuses the same RAW discovery knobs as MDIO ingest.

## Install

```bash
uv pip install -e ".[segy]"
# or
uv sync --extra segy
```

## API

```python
from segd.segy import segd_to_segy

segd_to_segy(
    raw_urls=["/path/R1.RAW", "/path/R2.RAW"],  # or a directory
    output_path="/path/out.segy",
    p190_path="/path/line.P190",  # optional
    sample_format="ieee",         # default; or "ibm"
    overwrite=False,
)
```

CLI:

```bash
segd segy export R037943.RAW R037944.RAW \
  --p190 Seq014.P190 \
  -o /tmp/out.segy \
  --sample-format ieee \
  --overwrite

# Directory scan
segd segy export /data/reel --prefix R --suffix RAW -o /tmp/out.segy
```

## Behaviour

- Writes textual + binary headers once, then **appends** trace chunks sequentially
  (default chunk = one RAW record / channel count). Sample volumes are never fully
  loaded into the parent process.
- Default sample format is **IEEE float32** (SEG-Y format code 5), matching SEG-D
  8058. Pass `sample_format="ibm"` for IBM float32 (format code 1).
- **P190 is optional.** When provided, logical source/receiver coordinates are
  joined into SEG-Y trace headers (`coordinate_scalar=-10`).
- Spec default is SEG-Y Rev 1, big-endian, EBCDIC text. Pass a custom `segy_spec`
  to override.

## Scale notes

- Suitable for reel-scale RAW lists; I/O cost is dominated by demux sample reads
  and SEG-Y encode/write.
- Rev0/Rev1 binary headers do not carry a live total-trace count field. Rev2+
  callers can supply a custom `segy_spec` / binary update if needed.
