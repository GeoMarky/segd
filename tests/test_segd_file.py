"""SegdFile and factory tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from segd import SegdFactory
from segd import SegdFile
from segd.catalog import collect_raw_urls
from segd.config import SegdHeaderOverrides
from segd.exceptions import UnsupportedFormatError
from segd.inference import parse_record_headers


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


@pytest.mark.casie21
def test_casie21_single_raw(casie21_paths: dict[str, Path]) -> None:
    sf = SegdFile(str(casie21_paths["raw1"]))
    assert sf.num_traces == 960
    assert sf.samples_per_trace == 7500
    assert sf.sample_interval == 2000
    assert int(sf.sample_labels[1]) == 2000
    assert int(sf.header[0]["orig_field_record_num"]) == 37943
    assert int(sf.header[0]["energy_source_point_num"]) == 54007


@pytest.mark.casie21
def test_casie21_two_raws_with_p190(casie21_paths: dict[str, Path]) -> None:
    sf = SegdFile(
        [str(casie21_paths["raw1"]), str(casie21_paths["raw2"])],
        navigation=str(casie21_paths["p190"]),
    )
    assert sf.num_traces == 1920
    h0 = sf.header[0]
    assert int(h0["source_coord_x"]) == 7417100
    assert int(h0["group_coord_x"]) == 7415303
    assert int(h0["coordinate_scalar"]) == -10
    h960 = sf.header[960]
    assert int(h960["orig_field_record_num"]) == 37944
    assert int(h960["trace_num_orig_record"]) == 1


@pytest.mark.casie21
def test_collect_raw_urls_skips_eot(casie21_paths: dict[str, Path]) -> None:
    urls = collect_raw_urls(casie21_paths["tape75"])
    assert urls
    assert all(not u.upper().endswith("EOT.RAW") for u in urls)
