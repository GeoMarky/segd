"""P190 parser / factory tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from segd.p190 import P190Factory
from segd.p190 import P190File
from segd.p190.parser import parse_point_line
from segd.p190.parser import parse_receiver_line
from segd.p190.schema import PointRecord
from segd.p190.schema import ReceiverGroup
from segd.p190.schema import ShotGather


def test_parse_point_and_receiver_packed() -> None:
    source = parse_point_line(
        "SMGL2104PD19    11  54007421148.70N1260421.01W "
        "741710.04675783.42804.2168140716.796010"
    )
    assert source.point_number == 54007
    assert source.easting == pytest.approx(741710.0)
    assert source.northing == pytest.approx(4675783.4)
    assert source.water_depth == pytest.approx(2804.2)
    assert source.day_of_year == 168
    assert source.time_hhmmss == "140716"
    assert source.time_ms == 796

    groups = parse_receiver_line(
        "R   1 741530.34675751.315.2   2 741517.74675751.015.2   3 741505.24675750.715.2"
    )
    assert len(groups) == 3
    assert groups[0].group_number == 1
    assert groups[0].easting == pytest.approx(741530.3)


def test_p190_factory_roundtrip(tmp_path: Path) -> None:
    source = PointRecord(
        record_type="S",
        line_name="TESTLINE",
        point_number=100,
        point_index=1,
        latitude_raw="421148.70N",
        longitude_raw="1260421.01W",
        easting=1000.0,
        northing=2000.0,
        water_depth=50.0,
        day_of_year=10,
        time_hhmmss="010203",
        time_ms=123,
        raw=(
            "STESTLINE       1  00100421148.70N1260421.01W "
            "1000.02000.050.0010010203.123000"
        ),
    )
    receivers = tuple(
        ReceiverGroup(group_number=i, easting=1000.0 + i, northing=2000.0, depth=10.0)
        for i in range(1, 7)
    )
    shot = ShotGather(
        line_name="TESTLINE",
        shot_point=100,
        source=source,
        vessel=None,
        echo=None,
        antennas=(),
        gun=None,
        tail=None,
        receivers=receivers,
    )
    path = tmp_path / "test.P190"
    factory = P190Factory(headers=["H0100SURVEY AREA                Test"])
    factory.to_file(str(path), [shot])

    nav = P190File(str(path))
    assert nav.num_shots == 1
    assert nav.num_groups == 6
    assert int(nav.shots[0]["shot_point"]) == 100
    assert float(nav.shots[0]["easting"]) == pytest.approx(1000.0)
    assert float(nav.receivers[0, 0, 0]) == pytest.approx(1001.0)
