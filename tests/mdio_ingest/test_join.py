"""Tests for RAW ↔ P190 join."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from segd import SegdFactory
from segd.catalog import build_catalog
from segd.exceptions import NavigationJoinError
from segd.p190 import P190Factory
from segd.p190.schema import PointRecord
from segd.p190.schema import ReceiverGroup
from segd.p190.schema import ShotGather

pytest.importorskip("mdio")

from segd.mdio.join import join_catalog_to_p190  # noqa: E402
from segd.p190 import P190File  # noqa: E402


def _make_shot(shot_point: int, n_recv: int, line: str = "LINE") -> ShotGather:
    source = PointRecord(
        record_type="S",
        line_name=line,
        point_number=shot_point,
        point_index=1,
        latitude_raw="421148.70N",
        longitude_raw="1260421.01W",
        easting=1000.0,
        northing=2000.0,
        water_depth=50.0,
        day_of_year=10,
        time_hhmmss="010203",
        time_ms=0,
        raw="",
    )
    receivers = tuple(
        ReceiverGroup(group_number=i, easting=1000.0 + i, northing=2000.0, depth=10.0)
        for i in range(1, n_recv + 1)
    )
    return ShotGather(
        line_name=line,
        shot_point=shot_point,
        source=source,
        vessel=None,
        echo=None,
        antennas=(),
        gun=None,
        tail=None,
        receivers=receivers,
    )


def test_join_catalog_to_p190(tmp_path: Path) -> None:
    factory = SegdFactory(
        samples_per_trace=8, channels_per_record=4, sample_interval=2000
    )
    samples = np.arange(32, dtype=np.float32).reshape(4, 8)
    raw = tmp_path / "shot.RAW"
    factory.to_file(str(raw), samples, file_number=1, shot_point=55, day_of_year=10)

    p190 = tmp_path / "nav.P190"
    P190Factory(headers=["H0100TEST"]).to_file(str(p190), [_make_shot(55, 4)])

    catalog = build_catalog(str(raw))
    nav = P190File(str(p190))
    mapping = join_catalog_to_p190(catalog, nav)
    assert mapping == {0: 0}


def test_join_missing_shot_raises(tmp_path: Path) -> None:
    factory = SegdFactory(
        samples_per_trace=8, channels_per_record=4, sample_interval=2000
    )
    samples = np.zeros((4, 8), dtype=np.float32)
    raw = tmp_path / "shot.RAW"
    factory.to_file(str(raw), samples, file_number=1, shot_point=99, day_of_year=10)

    p190 = tmp_path / "nav.P190"
    P190Factory(headers=["H0100TEST"]).to_file(str(p190), [_make_shot(55, 4)])

    catalog = build_catalog(str(raw))
    nav = P190File(str(p190))
    with pytest.raises(NavigationJoinError, match="not found"):
        join_catalog_to_p190(catalog, nav)
