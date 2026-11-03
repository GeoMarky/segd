"""SegdFile and factory tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from segd import SegdFactory
from segd import SegdFile
from segd.catalog import collect_raw_urls
from segd.catalog import resolve_raw_urls
from segd.config import SegdFileSettings
from segd.config import SegdHeaderOverrides
from segd.exceptions import NavigationJoinError
from segd.exceptions import UnsupportedFormatError
from segd.inference import parse_record_headers
from segd.p190 import P190Factory
from segd.p190.schema import PointRecord
from segd.p190.schema import ReceiverGroup
from segd.p190.schema import ShotGather
from segd.schema import Endianness


def _mock_shot(shot_point: int, n_recv: int, line: str = "LINE") -> ShotGather:
    source = PointRecord(
        record_type="S",
        line_name=line,
        point_number=shot_point,
        point_index=1,
        latitude_raw="421148.70N",
        longitude_raw="1260421.01W",
        easting=741710.0,
        northing=4675783.4,
        water_depth=2804.2,
        day_of_year=10,
        time_hhmmss="010203",
        time_ms=0,
        raw="",
    )
    receivers = tuple(
        ReceiverGroup(
            group_number=i,
            easting=741530.3 - (i - 1) * 12.6,
            northing=4675751.3,
            depth=15.2,
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


def test_tiny_segd_roundtrip(tiny_segd_record: str) -> None:
    sf = SegdFile(tiny_segd_record)
    assert sf.num_traces == 4
    assert sf.samples_per_trace == 8
    assert sf.sample_interval == 2000
    assert int(sf.sample_labels[1]) == 2000
    assert int(sf.header[0]["orig_field_record_num"]) == 100
    assert int(sf.header[0]["energy_source_point_num"]) == 55
    assert int(sf.header[3]["trace_num_orig_record"]) == 4
    np.testing.assert_allclose(sf.sample[0][:3], [0, 1, 2])
    trace = sf.trace[1]
    assert trace.sample.shape == (8,)
    assert int(trace.header["trace_num_orig_record"]) == 2
    assert sf.binary_header.to_dict()["format_code"] == 8058


def test_multi_file_catalog(mock_filesystem: str) -> None:
    factory = SegdFactory(
        samples_per_trace=4,
        channels_per_record=2,
        sample_interval=2000,
        trace_header_size=248,
    )
    urls = []
    for i, ffid in enumerate((10, 11)):
        samples = np.full((2, 4), float(i), dtype=np.float32)
        url = f"{mock_filesystem}shot{i}.RAW"
        factory.to_file(url, samples, file_number=ffid, shot_point=100 + i)
        urls.append(url)

    sf = SegdFile(urls)
    assert sf.num_traces == 4
    assert sf.num_records == 2
    assert int(sf.header[2]["orig_field_record_num"]) == 11
    assert int(sf.header[2]["trace_num_orig_record"]) == 1
    np.testing.assert_allclose(sf.sample[2][0], 1.0)


def test_multi_file_with_p190(tmp_path: Path) -> None:
    n_chan, n_samp = 4, 8
    factory = SegdFactory(
        samples_per_trace=n_samp,
        channels_per_record=n_chan,
        sample_interval=2000,
    )
    urls: list[str] = []
    shots: list[ShotGather] = []
    for i, shot_point in enumerate((54007, 54008), start=1):
        samples = np.full((n_chan, n_samp), float(i), dtype=np.float32)
        url = tmp_path / f"R{i:06d}.RAW"
        factory.to_file(
            str(url),
            samples,
            file_number=100 + i,
            shot_point=shot_point,
            day_of_year=10,
        )
        urls.append(str(url))
        shots.append(_mock_shot(shot_point, n_chan))

    p190 = tmp_path / "nav.P190"
    P190Factory(headers=["H0100TEST"]).to_file(str(p190), shots)

    sf = SegdFile(urls, navigation=str(p190))
    assert sf.num_traces == n_chan * 2
    h0 = sf.header[0]
    assert int(h0["source_coord_x"]) == 7417100
    assert int(h0["group_coord_x"]) == 7415303
    assert int(h0["coordinate_scalar"]) == -10
    assert int(sf.header[n_chan]["orig_field_record_num"]) == 102
    assert int(sf.header[n_chan]["trace_num_orig_record"]) == 1
    assert int(sf.header[n_chan]["shot_point"]) == 54008


def test_header_overrides(tiny_segd_record: str) -> None:
    overrides = SegdHeaderOverrides(trace_header={"ensemble_num": 999})
    sf = SegdFile(tiny_segd_record, header_overrides=overrides)
    assert int(sf.header[0]["ensemble_num"]) == 999


def test_unsupported_format_raises() -> None:
    buf = bytearray(128)
    buf[2:4] = bytes.fromhex("8015")  # multiplexed, unsupported
    with pytest.raises(UnsupportedFormatError):
        parse_record_headers(bytes(buf) + b"\xff\xff\x01\x01" + bytes(100), 256)


def test_factory_preserves_template_headers(tiny_segd_record: str) -> None:
    sf = SegdFile(tiny_segd_record)
    original = sf.read_record_bytes(0)
    factory = SegdFactory(
        samples_per_trace=8,
        channels_per_record=4,
        sample_interval=2000,
        trace_header_size=248,
    )
    samples = np.ones((4, 8), dtype=np.float32)
    rewritten = factory.create_record(
        samples,
        file_number=100,
        shot_point=55,
        template_record=original,
    )
    assert rewritten[:128] != b""
    assert len(rewritten) == len(original)


def test_collect_raw_urls_skips_eot(tmp_path: Path) -> None:
    factory = SegdFactory(
        samples_per_trace=4,
        channels_per_record=2,
        sample_interval=2000,
    )
    samples = np.zeros((2, 4), dtype=np.float32)
    factory.to_file(str(tmp_path / "R000001.RAW"), samples, file_number=1, shot_point=1)
    factory.to_file(str(tmp_path / "R000002.RAW"), samples, file_number=2, shot_point=2)
    (tmp_path / "EOT.RAW").write_bytes(b"end-of-tape-marker" * 8)

    urls = collect_raw_urls(tmp_path)
    assert len(urls) == 2
    assert all(not Path(u).name.upper().endswith("EOT.RAW") for u in urls)


def test_collect_raw_urls_custom_prefix_suffix(tmp_path: Path) -> None:
    factory = SegdFactory(
        samples_per_trace=4,
        channels_per_record=2,
        sample_interval=2000,
    )
    samples = np.zeros((2, 4), dtype=np.float32)
    factory.to_file(str(tmp_path / "SHOT001.sgd"), samples, file_number=1, shot_point=1)
    factory.to_file(str(tmp_path / "SHOT002.sgd"), samples, file_number=2, shot_point=2)
    factory.to_file(str(tmp_path / "R000003.RAW"), samples, file_number=3, shot_point=3)
    (tmp_path / "EOT.sgd").write_bytes(b"end-of-tape-marker" * 8)

    urls = collect_raw_urls(tmp_path, prefix="SHOT", suffix="sgd")
    assert len(urls) == 2
    assert all(Path(u).suffix.lower() == ".sgd" for u in urls)
    assert all(Path(u).name.startswith("SHOT") for u in urls)


def test_resolve_raw_urls_from_file_list(tmp_path: Path) -> None:
    factory = SegdFactory(
        samples_per_trace=4,
        channels_per_record=2,
        sample_interval=2000,
    )
    samples = np.zeros((2, 4), dtype=np.float32)
    names = ["R000001.RAW", "R000002.RAW"]
    for i, name in enumerate(names, start=1):
        factory.to_file(str(tmp_path / name), samples, file_number=i, shot_point=i)

    list_path = tmp_path / "shots.txt"
    list_path.write_text(
        "# selected shots\nR000002.RAW\nR000001.RAW\n", encoding="utf-8"
    )

    urls = resolve_raw_urls(tmp_path, file_list=list_path)
    assert [Path(u).name for u in urls] == ["R000002.RAW", "R000001.RAW"]

    urls_explicit = resolve_raw_urls([tmp_path / names[0], tmp_path / names[1]])
    assert len(urls_explicit) == 2


def test_zero_step_slices_are_rejected(tiny_segd_record: str) -> None:
    segd_file = SegdFile(tiny_segd_record)
    with pytest.raises(ValueError, match="Step of 0"):
        _ = segd_file.header[::0]
    with pytest.raises(ValueError, match="Step of 0"):
        _ = segd_file.trace[::0]


def test_trace_slice_returns_each_selected_trace(tiny_segd_record: str) -> None:
    traces = SegdFile(tiny_segd_record).trace[[0, 1]]
    assert traces.sample.shape[0] == 2


def test_raw_trace_fetch_returns_physical_bytes(tiny_segd_record: str) -> None:
    segd_file = SegdFile(tiny_segd_record)
    raw = segd_file.trace.fetch(np.array([0]), raw=True)
    assert raw.nbytes > 0
    assert segd_file.trace._fetch_raw(np.array([], dtype=np.int64)).size == 0


def test_endianness_and_binary_header_overrides(tiny_segd_record: str) -> None:
    segd_file = SegdFile(
        tiny_segd_record,
        settings=SegdFileSettings(endianness=Endianness.BIG),
        header_overrides=SegdHeaderOverrides(
            binary_header={"format_code": 8058},
            trace_header={"orig_field_record_num": 7},
        ),
    )
    assert segd_file.spec.endianness is Endianness.BIG
    assert int(segd_file.binary_header["format_code"]) == 8058
    assert int(segd_file.header[0]["orig_field_record_num"]) == 7


def test_navigation_join_reports_a_missing_shot_or_receiver_count(
    tiny_segd_record: str,
    tmp_path: Path,
) -> None:
    missing = _mock_shot(999, 4)
    path = tmp_path / "nav.P190"
    P190Factory(headers=["H0100TEST"]).to_file(str(path), [missing])
    segd_file = SegdFile(tiny_segd_record, navigation=str(path))
    with pytest.raises(NavigationJoinError, match="not found"):
        _ = segd_file.header[0]

    short = _mock_shot(55, 1)
    path.write_text(
        P190Factory(headers=["H0100TEST"]).create([short]), encoding="utf-8"
    )
    segd_file = SegdFile(tiny_segd_record, navigation=str(path))
    with pytest.raises(NavigationJoinError, match="receivers"):
        _ = segd_file.header[0]
