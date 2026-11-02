# Contributing

```bash
uv sync
uv run pytest
uv run nox
```

Please keep the public API aligned with `segy` where practical, and extend
`RecordCatalog` carefully when adding multi-file behaviour.
