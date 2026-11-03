"""SEG-D factory edge cases."""

from __future__ import annotations

import numpy as np
import pytest

from segd import SegdFactory


def _small_factory() -> SegdFactory:
    return SegdFactory(samples_per_trace=4, channels_per_record=1, sample_interval=2000)


def test_textual_header_uses_the_default_summary() -> None:
    assert _small_factory().create_textual_header().startswith(b"$11")


def test_binary_header_grows_a_short_template() -> None:
    header = _small_factory().create_binary_header(template_file_header=b"\x00" * 40)
    assert len(header) >= 128


def test_trace_header_template_is_padded_to_the_demux_size() -> None:
    factory = _small_factory()
    header = factory.create_trace_header(channel=1, template=b"\x00" * 4)
    assert len(header) == factory.trace_header_size


def test_create_traces_accepts_a_single_channel_vector() -> None:
    payload = _small_factory().create_traces(np.arange(4, dtype=np.float32))
    assert len(payload) > 4


def test_create_traces_checks_channel_and_sample_counts() -> None:
    factory = _small_factory()
    with pytest.raises(ValueError, match="channels"):
        factory.create_traces(np.zeros((2, 4), dtype=np.float32))
    with pytest.raises(ValueError, match="samples"):
        factory.create_traces(np.zeros((1, 2), dtype=np.float32))


def test_create_record_requires_demux_magic_in_a_template() -> None:
    with pytest.raises(ValueError, match="magic"):
        _small_factory().create_record(
            np.zeros((1, 4), dtype=np.float32),
            template_record=b"nope",
        )


def test_create_record_rewrites_samples_inside_a_template() -> None:
    factory = _small_factory()
    record = factory.create_record(
        np.arange(4, dtype=np.float32),
        file_number=3,
        shot_point=8,
    )
    rewritten = factory.create_record(
        np.ones((1, 4), dtype=np.float32),
        template_record=record,
        file_number=3,
    )
    assert rewritten[:4] == record[:4]
