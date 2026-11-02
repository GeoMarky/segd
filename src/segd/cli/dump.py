"""Dump subcommands for SEG-D / P190."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Annotated

import typer

from segd.cli.common import NavOpt
from segd.cli.common import UrlArg
from segd.exceptions import SegdError

if TYPE_CHECKING:
    from segd import SegdFile

app = typer.Typer(name="dump", help="Dump SEG-D headers and traces.")


def _open_segd(url: str, navigation: str | None) -> SegdFile:
    from segd import SegdFile  # noqa: PLC0415

    return SegdFile(url, navigation=navigation)


@app.command("info")
def dump_info(url: UrlArg, navigation: NavOpt = None) -> None:
    """Dump high-level file information."""
    try:
        sf = _open_segd(url, navigation)
    except SegdError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    payload = {
        "url": sf.url,
        "num_records": sf.num_records,
        "num_traces": sf.num_traces,
        "samples_per_trace": sf.samples_per_trace,
        "sample_interval_us": sf.sample_interval,
        "file_size": sf.file_size,
        "format": sf.spec.segd_standard.value,
    }
    typer.echo(json.dumps(payload, indent=2))


@app.command("text_header")
def dump_text_header(url: UrlArg, navigation: NavOpt = None) -> None:
    """Dump textual / external header summary."""
    sf = _open_segd(url, navigation)
    typer.echo(sf.text_header)


@app.command("binary_header")
def dump_binary_header(url: UrlArg, navigation: NavOpt = None) -> None:
    """Dump logical binary header as JSON."""
    sf = _open_segd(url, navigation)
    typer.echo(sf.binary_header.to_json())


@app.command("trace_header")
def dump_trace_header(
    url: UrlArg,
    index: Annotated[int, typer.Option("--index", "-i", help="Trace index.")] = 0,
    navigation: NavOpt = None,
) -> None:
    """Dump one logical trace header as JSON."""
    sf = _open_segd(url, navigation)
    typer.echo(sf.header[index].to_json())


@app.command("trace_data")
def dump_trace_data(
    url: UrlArg,
    index: Annotated[int, typer.Option("--index", "-i", help="Trace index.")] = 0,
    samples: Annotated[int, typer.Option(help="Number of samples to print.")] = 8,
    navigation: NavOpt = None,
) -> None:
    """Dump the first N samples of a trace."""
    sf = _open_segd(url, navigation)
    data = sf.sample[index]
    typer.echo(data[:samples].tolist())


@app.command("trace")
def dump_trace(
    url: UrlArg,
    index: Annotated[int, typer.Option("--index", "-i", help="Trace index.")] = 0,
    navigation: NavOpt = None,
) -> None:
    """Dump header JSON plus sample count for one trace."""
    sf = _open_segd(url, navigation)
    trace = sf.trace[index]
    typer.echo(trace.header.to_json())
    typer.echo(f"samples: {len(trace.sample)}")


@app.command("navigation")
def dump_navigation(
    url: Annotated[str, typer.Argument(help="Path to a P190 file.")],
) -> None:
    """Dump P190 shot / receiver summary."""
    from segd.p190 import P190File  # noqa: PLC0415

    nav = P190File(url)
    payload = {
        "num_shots": nav.num_shots,
        "num_groups": nav.num_groups,
        "first_shot_point": int(nav.shots[0]["shot_point"]) if nav.num_shots else None,
        "first_source_xy": (
            float(nav.shots[0]["easting"]),
            float(nav.shots[0]["northing"]),
        )
        if nav.num_shots
        else None,
    }
    typer.echo(json.dumps(payload, indent=2))
