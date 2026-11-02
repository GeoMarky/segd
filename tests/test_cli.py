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
