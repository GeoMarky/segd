"""Mock SEG-D → SEG-Y export tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from segd import SegdFactory
from segd.p190 import P190Factory
from segd.p190.schema import PointRecord
from segd.p190.schema import ReceiverGroup
from segd.p190.schema import ShotGather

pytest.importorskip("segy")

from segy import SegyFile  # noqa: E402
from segy.standards.codes import DataSampleFormatCode  # noqa: E402

from segd.segy import segd_to_segy  # noqa: E402
from segd.segy.pipeline import resolve_sample_format  # noqa: E402


def _shot(shot_point: int, n_recv: int, line: str = "LINEA") -> ShotGather:
    source = PointRecord(
        record_type="S",
        line_name=line,
        point_number=shot_point,
        point_index=1,
        latitude_raw="421148.70N",
        longitude_raw="1260421.01W",
        easting=741710.0,
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


def _write_two_raws(tmp_path: Path) -> tuple[list[str], int, int]:
    n_chan, n_samp = 4, 8
    factory = SegdFactory(
        samples_per_trace=n_samp,
        channels_per_record=n_chan,
        sample_interval=2000,
    )
    raw_urls: list[str] = []
    for i, shot_point in enumerate((100, 101), start=1):
        samples = (np.arange(n_chan * n_samp, dtype=np.float32) + 10 * i).reshape(
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
    return raw_urls, n_chan, n_samp


def test_resolve_sample_format() -> None:
    from segy.schema import ScalarType

    assert resolve_sample_format("ieee") is ScalarType.FLOAT32
    assert resolve_sample_format("ibm") is ScalarType.IBM32
    with pytest.raises(ValueError, match="Unknown sample_format"):
        resolve_sample_format("int16")


def test_segd_to_segy_ieee_without_p190(tmp_path: Path) -> None:
    raw_urls, n_chan, n_samp = _write_two_raws(tmp_path)
    out = tmp_path / "out_ieee.segy"
    segd_to_segy(
        raw_urls,
        out,
        sample_format="ieee",
        overwrite=True,
        progress=False,
    )

    sf = SegyFile(str(out))
    assert sf.num_traces == n_chan * 2
    assert sf.samples_per_trace == n_samp
    assert int(np.asarray(sf.binary_header["data_sample_format"]).item()) == int(
        DataSampleFormatCode.FLOAT32
    )
    samples = np.asarray(sf.sample[:])
    assert samples.shape == (n_chan * 2, n_samp)
    np.testing.assert_allclose(samples[0, :3], [10, 11, 12], rtol=1e-5)
    assert int(sf.header[0]["orig_field_record_num"]) == 1
    assert int(sf.header[0]["energy_source_point_num"]) == 100
    assert int(sf.header[n_chan]["orig_field_record_num"]) == 2


def test_segd_to_segy_with_p190_coords(tmp_path: Path) -> None:
    raw_urls, n_chan, _n_samp = _write_two_raws(tmp_path)
    shots = [_shot(100, n_chan), _shot(101, n_chan)]
    p190 = tmp_path / "nav.P190"
    P190Factory(headers=["H0100TEST"]).to_file(str(p190), shots)

    out = tmp_path / "out_nav.segy"
    segd_to_segy(
        raw_urls,
        out,
        p190_path=p190,
        sample_format="ieee",
        overwrite=True,
        progress=False,
    )

    sf = SegyFile(str(out))
    h0 = sf.header[0]
    assert int(h0["coordinate_scalar"]) == -10
    assert int(h0["source_coord_x"]) == 7417100
    assert int(h0["group_coord_x"]) == 7415310  # 741530 + 1 group, *10


def test_segd_to_segy_ibm(tmp_path: Path) -> None:
    raw_urls, n_chan, n_samp = _write_two_raws(tmp_path)
    out = tmp_path / "out_ibm.segy"
    segd_to_segy(
        raw_urls,
        out,
        sample_format="ibm",
        overwrite=True,
        progress=False,
    )
    sf = SegyFile(str(out))
    assert int(np.asarray(sf.binary_header["data_sample_format"]).item()) == int(
        DataSampleFormatCode.IBM32
    )
    samples = np.asarray(sf.sample[:n_chan])
    assert samples.shape == (n_chan, n_samp)
    assert np.isfinite(samples).all()


def test_overwrite_guard(tmp_path: Path) -> None:
    raw_urls, _, _ = _write_two_raws(tmp_path)
    out = tmp_path / "exists.segy"
    out.write_bytes(b"placeholder")
    with pytest.raises(FileExistsError):
        segd_to_segy(raw_urls, out, overwrite=False, progress=False)
