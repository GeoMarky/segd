"""SEG-D Typer application entry point."""

from __future__ import annotations

import typer

from segd.cli.dump import app as dump_app
from segd.cli.mdio import app as mdio_app

app = typer.Typer(
    name="segd",
    help="SEG-D and UKOOA P1/90 inspection utilities.",
    no_args_is_help=True,
)
app.add_typer(dump_app, name="dump")
app.add_typer(mdio_app, name="mdio")


def main() -> None:
    """Console script entry."""
    app()


if __name__ == "__main__":
    main()
