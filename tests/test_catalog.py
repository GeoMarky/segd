"""Catalog scanning, file lists, and record ordering."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from typing import cast

import numpy as np
import pytest

from segd import SegdFactory
from segd.catalog import RecordCatalog
from segd.catalog import RecordEntry
from segd.catalog import build_catalog
from segd.catalog import collect_raw_urls
from segd.catalog import read_file_list
from segd.catalog import resolve_raw_urls
from segd.config import RecordOrder
from segd.exceptions import SegdFileSpecMismatchError
from segd.inference import GeneralHeaderInfo


def test_empty_catalog_has_no_traces() -> None:
    catalog = RecordCatalog(records=[])
    assert catalog.num_traces == 0
    with pytest.raises(IndexError, match="out of range"):
        catalog.locate(0)


def test_locate_rejects_an_index_that_falls_in_a_gap() -> None:
    # The catalog length comes from the last record, so an early hole is in range
    # but does not belong to any record.
    info = cast(GeneralHeaderInfo, SimpleNamespace(channels=1))
    record = RecordEntry(
        url="a",
        fs=cast(Any, None),
        info=info,
        global_trace_start=5,
        file_size=1,
    )
    catalog = RecordCatalog(records=[record])
    with pytest.raises(IndexError, match="Failed to locate"):
        catalog.locate(0)


def test_collect_raw_urls_skips_small_files_and_honors_a_pattern(
    tmp_path: Path,
) -> None:
    (tmp_path / "R1.RAW").write_bytes(b"x" * 80)
    (tmp_path / "R2.raw").write_bytes(b"y" * 10)
    (tmp_path / "EOT.RAW").write_bytes(b"z" * 80)
    (tmp_path / "other.DAT").write_bytes(b"q" * 80)

    assert collect_raw_urls(tmp_path, suffix=".RAW") == [str(tmp_path / "R1.RAW")]
    assert collect_raw_urls(tmp_path, pattern="*.DAT") == [str(tmp_path / "other.DAT")]


def test_read_file_list_resolves_relative_names_and_keeps_absolute_paths(
    tmp_path: Path,
) -> None:
    absolute = tmp_path / "elsewhere" / "shot.RAW"
    listing = tmp_path / "files.txt"
    listing.write_text(
        f"# comment\n\nR1.RAW\n{absolute}\n",
        encoding="utf-8",
    )

    urls = read_file_list(listing, base_dir=tmp_path)
    assert urls == [str(tmp_path / "R1.RAW"), str(absolute)]


def test_read_file_list_rejects_a_file_with_no_names(tmp_path: Path) -> None:
    blank = tmp_path / "blank.txt"
    blank.write_text("# nothing\n", encoding="utf-8")
    with pytest.raises(ValueError, match="did not contain"):
        read_file_list(blank)


def test_resolve_raw_urls_accepts_a_directory_list_a_file_or_a_sequence(
    tmp_path: Path,
) -> None:
    listing = tmp_path / "files.txt"
    listing.write_text("R1.RAW\n", encoding="utf-8")

    assert resolve_raw_urls(tmp_path, file_list=listing) == [str(tmp_path / "R1.RAW")]
    assert resolve_raw_urls("memory://one.RAW") == ["memory://one.RAW"]
    assert resolve_raw_urls(["a.RAW", "b.RAW"]) == ["a.RAW", "b.RAW"]
    with pytest.raises(ValueError, match="Provide raw_urls"):
        resolve_raw_urls(None)


def _write_record(
    path: Path, *, channels: int, file_number: int, shot_point: int
) -> None:
    factory = SegdFactory(
        samples_per_trace=4,
        channels_per_record=channels,
        sample_interval=2000,
    )
    factory.to_file(
        str(path),
        np.zeros((channels, 4), dtype=np.float32),
        file_number=file_number,
        shot_point=shot_point,
    )


def test_build_catalog_orders_by_name_ffid_and_shot_point(tmp_path: Path) -> None:
    later = tmp_path / "b.RAW"
    earlier = tmp_path / "a.RAW"
    _write_record(later, channels=2, file_number=20, shot_point=2)
    _write_record(earlier, channels=2, file_number=10, shot_point=9)
    urls = [str(later), str(earlier)]

    assert Path(build_catalog(urls, order="name").urls[0]).name == "a.RAW"
    assert Path(build_catalog(urls, order=RecordOrder.FFID).urls[0]).name == "a.RAW"
    assert (
        Path(build_catalog(urls, order=RecordOrder.SHOT_POINT).urls[0]).name == "b.RAW"
    )


def test_build_catalog_requires_at_least_one_url() -> None:
    with pytest.raises(ValueError, match="At least one"):
        build_catalog([])


def test_build_catalog_rejects_mixed_geometry(tmp_path: Path) -> None:
    first = tmp_path / "a.RAW"
    second = tmp_path / "c.RAW"
    _write_record(first, channels=2, file_number=1, shot_point=1)
    _write_record(second, channels=3, file_number=2, shot_point=2)
    with pytest.raises(SegdFileSpecMismatchError):
        build_catalog([str(first), str(second)])
