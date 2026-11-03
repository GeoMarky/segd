"""CLI smoke tests."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from segd.cli.segd import app

runner = CliRunner()

# Typer's option highlighter emits ANSI between the two dashes of a long
# option when color is on (CI sets FORCE_COLOR / GITHUB_ACTIONS), so "--p190"
# is not a contiguous substring of the raw help text.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def test_cli_info(tiny_segd_record: str) -> None:
    result = runner.invoke(app, ["dump", "info", tiny_segd_record])
    assert result.exit_code == 0
    assert "num_traces" in result.stdout


def test_cli_binary_header(tiny_segd_record: str) -> None:
    result = runner.invoke(app, ["dump", "binary_header", tiny_segd_record])
    assert result.exit_code == 0
    assert "sample_interval" in result.stdout


def test_cli_mdio_help() -> None:
    result = runner.invoke(app, ["mdio", "import", "--help"])
    assert result.exit_code == 0
    stdout = _plain(result.stdout)
    assert "--p190" in stdout
    assert "--template" in stdout
    assert "--prefix" in stdout
    assert "--suffix" in stdout
    assert "--file-list" in stdout


def test_cli_segy_help() -> None:
    result = runner.invoke(app, ["segy", "export", "--help"])
    assert result.exit_code == 0
    stdout = _plain(result.stdout)
    assert "--p190" in stdout
    assert "--sample-format" in stdout
    assert "--prefix" in stdout
    assert "--suffix" in stdout
    assert "--file-list" in stdout
