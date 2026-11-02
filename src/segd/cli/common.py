"""Shared CLI helpers."""

from __future__ import annotations

from typing import Annotated

import typer

UrlArg = Annotated[str, typer.Argument(help="Path or URL to a SEG-D RAW file.")]
NavOpt = Annotated[
    str | None,
    typer.Option("--navigation", "-n", help="Optional P190 navigation path."),
]
