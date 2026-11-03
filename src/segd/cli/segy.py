"""CLI for SEG-D → SEG-Y export."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from typing import Literal

import typer

app = typer.Typer(name="segy", help="SEG-Y export commands (requires segd[segy]).")


@app.command("export")
def segy_export(  # noqa: PLR0913
    raw: Annotated[
        list[Path] | None,
        typer.Argument(
            help=(
                "SEG-D file(s), or a directory to scan. "
                "Optional when --file-list is provided."
            ),
        ),
    ] = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output SEG-Y path.")
    ] = ...,
    p190: Annotated[
        Path | None,
        typer.Option("--p190", help="Optional UKOOA P1/90 navigation file."),
    ] = None,
    file_list: Annotated[
        Path | None,
        typer.Option(
            "--file-list",
            help=(
                "Text file listing SEG-D filenames/paths (one per line). "
                "Relative names resolve against a directory RAW argument."
            ),
        ),
    ] = None,
    prefix: Annotated[
        str,
        typer.Option("--prefix", help="Filename prefix when scanning a directory."),
    ] = "R",
    suffix: Annotated[
        str,
        typer.Option(
            "--suffix",
            help="Filename suffix/extension when scanning a directory (default RAW).",
        ),
    ] = "RAW",
    pattern: Annotated[
        str | None,
        typer.Option(
            "--pattern",
            help="Optional glob overriding --prefix/--suffix for directory scans.",
        ),
    ] = None,
    sample_format: Annotated[
        Literal["ieee", "ibm"],
        typer.Option(
            "--sample-format",
            help="SEG-Y sample format (default ieee / float32).",
        ),
    ] = "ieee",
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Overwrite existing output.")
    ] = False,
) -> None:
    """Export SEG-D RAW records into a single SEG-Y file."""
    try:
        from segd.segy import segd_to_segy  # noqa: PLC0415
    except ImportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if not raw and file_list is None:
        typer.echo("Provide RAW path(s)/directory and/or --file-list.", err=True)
        raise typer.Exit(code=1)

    raw_urls: Path | list[Path] | None
    if raw is None or len(raw) == 0:
        raw_urls = None
    elif len(raw) == 1:
        raw_urls = raw[0]
    else:
        raw_urls = raw

    try:
        segd_to_segy(
            raw_urls=raw_urls,
            output_path=output,
            p190_path=p190,
            file_list=file_list,
            file_prefix=prefix,
            file_suffix=suffix,
            file_pattern=pattern,
            sample_format=sample_format,
            overwrite=overwrite,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"SEG-Y export failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Wrote SEG-Y file to {output}")
