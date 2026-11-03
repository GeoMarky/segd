"""CLI smoke tests."""

from __future__ import annotations

from typer.testing import CliRunner

from segd.cli.segd import app

runner = CliRunner()


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
    assert "--p190" in result.stdout
    assert "--template" in result.stdout
    assert "--prefix" in result.stdout
    assert "--suffix" in result.stdout
    assert "--file-list" in result.stdout


def test_cli_segy_help() -> None:
    result = runner.invoke(app, ["segy", "export", "--help"])
    assert result.exit_code == 0
    assert "--p190" in result.stdout
    assert "--sample-format" in result.stdout
    assert "--prefix" in result.stdout
    assert "--suffix" in result.stdout
    assert "--file-list" in result.stdout
