# CLI usage

```bash
segd dump info /path/to/shot.RAW
segd dump binary_header /path/to/shot.RAW
segd dump trace_header --index 0 /path/to/shot.RAW -n /path/to/line.P190
segd dump navigation /path/to/line.P190
```

```{typer} segd.cli.segd:app
:prog: segd
:show-nested:
```
