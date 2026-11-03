"""CLI smoke tests."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from segd.cli.segd import app
from segd.cli.segd import main
from segd.p190 import P190Factory
from segd.p190.schema import PointRecord
from segd.p190.schema import ReceiverGroup
from segd.p190.schema import ShotGather

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


def test_cli_dump_text_header(tiny_segd_record: str) -> None:
    result = runner.invoke(app, ["dump", "text_header", tiny_segd_record])
    assert result.exit_code == 0, result.output


def test_cli_dump_one_trace_header(tiny_segd_record: str) -> None:
    result = runner.invoke(
        app, ["dump", "trace_header", tiny_segd_record, "--index", "1"]
    )
    assert result.exit_code == 0, result.output


def test_cli_dump_trace_samples(tiny_segd_record: str) -> None:
    result = runner.invoke(
        app, ["dump", "trace_data", tiny_segd_record, "--index", "0"]
    )
    assert result.exit_code == 0, result.output


def test_cli_dump_trace_header_and_sample_count(tiny_segd_record: str) -> None:
    result = runner.invoke(app, ["dump", "trace", tiny_segd_record])
    assert result.exit_code == 0
    assert "samples:" in result.stdout


def test_cli_dump_navigation(tmp_path: Path) -> None:
    source = PointRecord(
        record_type="S",
        line_name="LINE",
        point_number=7,
        point_index=1,
        latitude_raw="421148.70N",
        longitude_raw="1260421.01W",
        easting=10.0,
        northing=20.0,
        water_depth=5.0,
        day_of_year=1,
        time_hhmmss="010203",
        time_ms=4,
        raw="",
    )
    shot = ShotGather(
        line_name="LINE",
        shot_point=7,
        source=source,
        vessel=None,
        echo=None,
        antennas=(),
        tail=None,
        gun=None,
        receivers=(ReceiverGroup(1, 1.0, 2.0, 3.0),),
    )
    path = tmp_path / "nav.P190"
    P190Factory(headers=["H0100TEST"]).to_file(str(path), [shot])

    result = runner.invoke(app, ["dump", "navigation", str(path)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["num_shots"] == 1


def test_main_exits_after_printing_help(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["segd", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_optional_commands_report_a_missing_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "mdio.builder.template_registry", None)
    mdio = runner.invoke(
        app,
        ["mdio", "import", "raw.RAW", "--p190", "nav.P190", "-o", "out.mdio"],
    )
    assert mdio.exit_code == 1

    monkeypatch.setitem(sys.modules, "segd.segy", None)
    segy = runner.invoke(app, ["segy", "export", "raw.RAW", "-o", "out.segy"])
    assert segy.exit_code == 1


def test_cli_segy_help() -> None:
    result = runner.invoke(app, ["segy", "export", "--help"])
    assert result.exit_code == 0
    stdout = _plain(result.stdout)
    assert "--p190" in stdout
    assert "--sample-format" in stdout
    assert "--prefix" in stdout
    assert "--suffix" in stdout
    assert "--file-list" in stdout
