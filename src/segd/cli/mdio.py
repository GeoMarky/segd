"""CLI for SEG-D + P190 → MDIO ingest."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from typing import cast

import typer

app = typer.Typer(name="mdio", help="MDIO ingest commands (requires segd[mdio]).")

# Typer treats an Ellipsis default as a required option. The cast keeps the
# parameter type as Path for mypy.
_REQUIRED_PATH = cast("Path", ...)


@app.command("import")
def mdio_import(  # noqa: PLR0913
    raw: Annotated[
        list[Path] | None,
        typer.Argument(
            help=(
                "SEG-D file(s), or a directory to scan. "
                "Optional when --file-list is provided."
            ),
        ),
    ] = None,
    p190: Annotated[
        Path, typer.Option("--p190", help="UKOOA P1/90 navigation file.")
    ] = _REQUIRED_PATH,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output MDIO path.")
    ] = _REQUIRED_PATH,
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
    template: Annotated[
        str,
        typer.Option("--template", "-t", help="MDIO template name."),
    ] = "StreamerShotGathers3D",
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Overwrite existing output.")
    ] = False,
    auto_shot_wrap: Annotated[
        bool,
        typer.Option("--auto-shot-wrap", help="Enable AutoShotWrap grid override."),
    ] = False,
    auto_channel_wrap: Annotated[
        bool,
        typer.Option(
            "--auto-channel-wrap", help="Enable AutoChannelWrap grid override."
        ),
    ] = False,
    cable: Annotated[int, typer.Option("--cable", help="Default cable id.")] = 1,
    gun: Annotated[int, typer.Option("--gun", help="Default gun id.")] = 1,
) -> None:
    """Ingest SEG-D RAW + P190 into an MDIO / Zarr dataset."""
    try:
        from mdio.builder.template_registry import get_template  # noqa: PLC0415
        from mdio.segy.geometry import GridOverrides  # noqa: PLC0415

        from segd.mdio import segd_to_mdio  # noqa: PLC0415
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

    overrides = GridOverrides(
        auto_shot_wrap=auto_shot_wrap,
        auto_channel_wrap=auto_channel_wrap,
    )
    if not overrides:
        overrides = None

    try:
        segd_to_mdio(
            mdio_template=get_template(template),
            raw_urls=raw_urls,
            p190_path=p190,
            output_path=output,
            file_list=file_list,
            file_prefix=prefix,
            file_suffix=suffix,
            file_pattern=pattern,
            overwrite=overwrite,
            grid_overrides=overrides,
            dim_defaults={"cable": cable, "gun": gun},
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"MDIO ingest failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Wrote MDIO dataset to {output}")
