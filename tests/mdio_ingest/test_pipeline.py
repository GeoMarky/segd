"""Mock SEG-D → MDIO ingest tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from segd import SegdFactory
from segd.p190 import P190Factory
from segd.p190.schema import PointRecord
from segd.p190.schema import ReceiverGroup
from segd.p190.schema import ShotGather

pytest.importorskip("mdio")

from mdio.api.io import open_mdio  # noqa: E402
from mdio.builder.template_registry import get_template  # noqa: E402

from segd.mdio import segd_to_mdio  # noqa: E402


def _shot(shot_point: int, n_recv: int, line: str = "LINEA") -> ShotGather:
    source = PointRecord(
        record_type="S",
        line_name=line,
        point_number=shot_point,
        point_index=1,
        latitude_raw="421148.70N",
        longitude_raw="1260421.01W",
        easting=741710.0 + shot_point,
        northing=4675783.0,
        water_depth=2800.0,
        day_of_year=10,
        time_hhmmss="010203",
        time_ms=0,
        raw="",
    )
    receivers = tuple(
        ReceiverGroup(
            group_number=i,
            easting=741530.0 + i,
            northing=4675751.0,
            depth=15.0,
        )
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


def test_synthetic_segd_to_mdio(tmp_path: Path) -> None:
    n_chan, n_samp = 4, 8
    factory = SegdFactory(
        samples_per_trace=n_samp,
        channels_per_record=n_chan,
        sample_interval=2000,
    )
    raw_urls: list[str] = []
    shots: list[ShotGather] = []
    for i, shot_point in enumerate((100, 101), start=1):
        samples = (np.arange(n_chan * n_samp, dtype=np.float32) + i).reshape(
            n_chan, n_samp
        )
        url = tmp_path / f"R{i:06d}.RAW"
        factory.to_file(
            str(url),
            samples,
            file_number=i,
            shot_point=shot_point,
            day_of_year=10,
        )
        raw_urls.append(str(url))
        shots.append(_shot(shot_point, n_chan))

    p190 = tmp_path / "synth.P190"
    P190Factory(headers=["H0100SYNTH"]).to_file(str(p190), shots)

    out = tmp_path / "synth.mdio"
    segd_to_mdio(
        mdio_template=get_template("StreamerShotGathers3D"),
        raw_urls=raw_urls,
        p190_path=p190,
        output_path=out,
        overwrite=True,
    )

    ds = open_mdio(str(out))
    assert "amplitude" in ds
    assert ds.amplitude.shape[0] == 2  # two shots
    assert ds.amplitude.shape[-1] == n_samp
    assert int(np.sum(ds.trace_mask.values)) == n_chan * 2
    assert "segd_file_header" in ds
