"""P190 parser / factory tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from segd.p190 import P190Factory
from segd.p190 import P190File
from segd.p190.parser import parse_p190_lines
from segd.p190.parser import parse_point_line
from segd.p190.parser import parse_receiver_line
from segd.p190.parser import shots_to_tables
from segd.p190.schema import PointRecord
from segd.p190.schema import ReceiverGroup
from segd.p190.schema import ShotGather
from segd.p190.writer import format_point_record
from segd.p190.writer import format_receiver_line
from segd.p190.writer import format_shot_gather


def _point(kind: str, number: int, *, raw: str = "") -> PointRecord:
    return PointRecord(
        record_type=kind,
        line_name="LINE",
        point_number=number,
        point_index=1,
        latitude_raw="421148.70N",
        longitude_raw="1260421.01W",
        easting=10.0,
        northing=20.0,
        water_depth=5.0,
        day_of_year=1,
        time_hhmmss="010203",
        time_ms=4,
        raw=raw,
    )


def _shot(
    *,
    shot_point: int = 7,
    receivers: tuple[ReceiverGroup, ...] = (ReceiverGroup(1, 1.0, 2.0, 3.0),),
) -> ShotGather:
    return ShotGather(
        line_name="LINE",
        shot_point=shot_point,
        source=_point("S", shot_point),
        vessel=None,
        echo=None,
        antennas=(),
        tail=None,
        gun=None,
        receivers=receivers,
    )


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


def test_format_point_record_builds_or_preserves_the_card() -> None:
    line = format_point_record(_point("S", 7))
    assert line[0] == "S"
    assert len(line) == 86

    preserved = format_point_record(_point("V", 1, raw="V" + ("x" * 85)))
    assert preserved.startswith("Vxxx")


def test_format_receiver_line_requires_one_to_three_groups() -> None:
    with pytest.raises(ValueError, match="1 to 3"):
        format_receiver_line(())

    line = format_receiver_line((ReceiverGroup(2, 1.5, 2.5, 3.25),))
    assert line.startswith("R")
    assert len(line) == 80


def test_format_shot_gather_includes_optional_points_and_receiver_cards() -> None:
    shot = ShotGather(
        line_name="LINE",
        shot_point=7,
        source=_point("S", 7),
        vessel=_point("V", 1),
        echo=_point("E", 1),
        antennas=(_point("A", 1),),
        gun=_point("Z", 1),
        tail=_point("C", 1),
        receivers=tuple(ReceiverGroup(i, float(i), 1.0, 1.0) for i in range(1, 5)),
    )
    rendered = format_shot_gather(shot)
    assert rendered[0][0] == "V"
    assert any(row.startswith("R") for row in rendered)


def test_parser_rejects_unknown_record_types() -> None:
    with pytest.raises(ValueError, match="Unrecognized"):
        parse_point_line("Qbad")
    with pytest.raises(ValueError, match="Expected R"):
        parse_receiver_line("S not a receiver")


def test_receiver_card_without_a_source_is_not_a_shot() -> None:
    headers, shots = parse_p190_lines(["H0100ONLY\n", "R   1 1.0 2.0 3.0\n"])
    assert headers == ["H0100ONLY"]
    assert shots == []


def test_shots_to_tables_empty_and_inconsistent_receiver_counts() -> None:
    empty_shots, empty_receivers = shots_to_tables([])
    assert len(empty_shots) == 0
    assert empty_receivers.shape[0] == 0
    with pytest.raises(ValueError, match="Inconsistent"):
        shots_to_tables([_shot(), _shot(receivers=())])


def test_shot_lookup_on_a_header_only_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.P190"
    path.write_text("H0100ONLY\n", encoding="utf-8")
    nav = P190File(str(path))
    assert nav.num_groups == 0
    with pytest.raises(KeyError, match="not found"):
        nav.shot_by_point(1)
