"""Indexing helper tests."""

from __future__ import annotations

import numpy as np
import pytest

from segd import SegdFile
from segd.indexing import HeaderIndexer
from segd.indexing import TraceIndexer
from segd.indexing import _trace_byte_range
from segd.indexing import bounds_check


def test_bounds_check_ok() -> None:
    bounds_check(np.asarray([0, 1, 2], dtype=np.int64), 3, "trace")


def test_bounds_check_raises() -> None:
    with pytest.raises(IndexError):
        bounds_check(np.asarray([-1], dtype=np.int64), 3, "trace")
    with pytest.raises(IndexError):
        bounds_check(np.asarray([3], dtype=np.int64), 3, "trace")


def test_trace_byte_range_can_select_header_or_samples(tiny_segd_record: str) -> None:
    catalog = SegdFile(tiny_segd_record).catalog
    full = _trace_byte_range(catalog, 0)
    header_only = _trace_byte_range(catalog, 0, header_only=True)
    data_only = _trace_byte_range(catalog, 0, data_only=True)
    assert header_only[3] - header_only[2] < full[3] - full[2]
    assert data_only[2] == header_only[3]


def test_header_and_trace_indexers_decode_one_record(tiny_segd_record: str) -> None:
    segd_file = SegdFile(tiny_segd_record)
    headers = HeaderIndexer(catalog=segd_file.catalog, spec=segd_file.spec.trace)
    fs, url, start, end = headers.indices_to_fetches(np.array([0]))[0]
    buf = bytearray(fs.read_block(url, offset=start, length=end - start))
    assert headers.decode(buf).dtype.names
    assert headers.decode(buf, raw=True).dtype.kind == "V"

    traces = TraceIndexer(catalog=segd_file.catalog, spec=segd_file.spec.trace)
    fs, url, start, end = traces.indices_to_fetches(np.array([0, 0]))[0]
    trace_buf = bytearray(fs.read_block(url, offset=start, length=end - start))
    assert traces.decode(trace_buf).dtype.names == ("header", "data")


def test_sample_indexer_rejects_an_empty_or_zero_step_slice(
    tiny_segd_record: str,
) -> None:
    segd_file = SegdFile(tiny_segd_record)
    with pytest.raises(ValueError, match="Step of 0"):
        _ = segd_file.sample[::0]
    with pytest.raises(IndexError):
        _ = segd_file.sample[0:0]


def test_duplicate_sample_index_is_still_readable(tiny_segd_record: str) -> None:
    segd_file = SegdFile(tiny_segd_record)
    samples = segd_file.sample[[0, 0]]
    assert samples.shape[-1] == segd_file.samples_per_trace
