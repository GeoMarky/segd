"""Parse UKOOA P1/90 (P190) navigation files."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import numpy as np

from segd.p190.schema import PointRecord
from segd.p190.schema import ReceiverGroup
from segd.p190.schema import ShotGather

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence

    from numpy.typing import NDArray

_POINT_TYPES = frozenset("SVEAZCT")
# Packed Spectra/SeisPos layout: shot digits are concatenated onto latitude.
_POINT_TAIL_RE = re.compile(
    r"(?P<head>.*?)"
    r"(?P<shot>\d{3,})"
    r"(?P<lat>\d{6}\.\d{2}[NS])"
    r"(?P<lon>\d{7}\.\d{2}[EW])"
    r"\s*"
    r"(?P<east>\d+\.\d)"
    r"\s*"
    r"(?P<north>\d+\.\d)"
    r"\s*"
    r"(?P<depth>\d+\.\d)"
    r"\s*"
    r"(?P<day>\d{3})"
    r"(?P<time>\d{6}\.\d{3})"
    r"(?P<trailer>.*)$"
)
# Easting/northing use one decimal in this P1/90 dialect; depth may have more
# and may be separated by spaces when values are not tightly packed.
_RECV_CHUNK_RE = re.compile(
    r"\s*(\d+)\s*"
    r"(\d+\.\d)\s*"
    r"(\d+\.\d)\s*"
    r"(\d+\.\d+)"
)


def parse_point_line(line: str) -> PointRecord:
    """Parse one V/E/A/S/Z/C/T record line."""
    raw = line.rstrip("\n\r")
    if not raw or raw[0] not in _POINT_TYPES:
        msg = f"Unrecognized P190 point record: {raw!r}"
        raise ValueError(msg)

    match = _POINT_TAIL_RE.match(raw)
    if match is None:
        msg = f"Unrecognized P190 point record: {raw!r}"
        raise ValueError(msg)

    record_type = raw[0]
    head = match.group("head")
    # head is like 'EMGL2104PD19    1 1 ' or 'SMGL2104PD19    11  '
    line_name = head[1:13].strip() if len(head) >= 13 else head[1:].strip()
    index_tokens = re.findall(r"\d+", head[13:])
    point_index = int(index_tokens[0]) if index_tokens else 1
    point_number = int(match.group("shot"))

    return PointRecord(
        record_type=record_type,
        line_name=line_name,
        point_number=point_number,
        point_index=point_index,
        latitude_raw=match.group("lat"),
        longitude_raw=match.group("lon"),
        easting=float(match.group("east")),
        northing=float(match.group("north")),
        water_depth=float(match.group("depth")),
        day_of_year=int(match.group("day")),
        time_hhmmss=match.group("time").split(".", maxsplit=1)[0],
        time_ms=int(match.group("time").split(".", maxsplit=1)[1]),
        raw=raw,
    )


def parse_receiver_line(line: str) -> list[ReceiverGroup]:
    """Parse one R card into up to three receiver groups."""
    raw = line.rstrip("\n\r")
    if not raw.startswith("R"):
        msg = f"Expected R record, got: {raw!r}"
        raise ValueError(msg)

    body = raw[1:]
    groups: list[ReceiverGroup] = []
    for match in _RECV_CHUNK_RE.finditer(body):
        groups.append(
            ReceiverGroup(
                group_number=int(match.group(1)),
                easting=float(match.group(2)),
                northing=float(match.group(3)),
                depth=float(match.group(4)),
            )
        )
    return groups


def parse_p190_lines(lines: Iterable[str]) -> tuple[list[str], list[ShotGather]]:
    """Parse header cards and shot gathers from P190 text lines."""
    headers: list[str] = []
    shots: list[ShotGather] = []

    current_points: dict[str, list[PointRecord]] = {}
    current_receivers: list[ReceiverGroup] = []

    def flush() -> None:
        nonlocal current_points, current_receivers
        if "S" not in current_points:
            current_points = {}
            current_receivers = []
            return
        source = current_points["S"][0]
        shots.append(
            ShotGather(
                line_name=source.line_name,
                shot_point=source.point_number,
                source=source,
                vessel=current_points.get("V", [None])[0],
                echo=current_points.get("E", [None])[0],
                antennas=tuple(current_points.get("A", [])),
                gun=current_points.get("Z", [None])[0],
                tail=current_points.get("T", [None])[0],
                receivers=tuple(current_receivers),
            )
        )
        current_points = {}
        current_receivers = []

    for line in lines:
        if not line or line.isspace():
            continue
        record_id = line[0]
        if record_id == "H":
            headers.append(line.rstrip("\n\r"))
            continue
        if record_id in _POINT_TYPES:
            if record_id in {"V", "S"} and current_receivers and "S" in current_points:
                flush()
            point = parse_point_line(line)
            current_points.setdefault(point.record_type, []).append(point)
            continue
        if record_id == "R":
            current_receivers.extend(parse_receiver_line(line))
            continue

    flush()
    return headers, shots


def shots_to_tables(
    shots: Sequence[ShotGather],
) -> tuple[NDArray[np.void], NDArray[np.float64]]:
    """Convert shot gathers to a shot structured array and receivers array.

    Args:
        shots: Shot gathers to tabulate.

    Returns:
        shot_table: structured array with shot metadata
        receivers: shape (n_shots, n_groups, 3) as easting, northing, depth

    Raises:
        ValueError: If the shots do not all have the same receiver count.
    """
    if not shots:
        empty_shots = np.zeros(
            0,
            dtype=[
                ("line_name", "U32"),
                ("shot_point", "i4"),
                ("easting", "f8"),
                ("northing", "f8"),
                ("water_depth", "f8"),
                ("day_of_year", "i4"),
                ("time_hhmmss", "U8"),
                ("time_ms", "i4"),
            ],
        )
        return empty_shots, np.zeros((0, 0, 3), dtype=np.float64)

    n_groups = len(shots[0].receivers)
    for shot in shots:
        if len(shot.receivers) != n_groups:
            msg = (
                f"Inconsistent receiver count for shot {shot.shot_point}: "
                f"{len(shot.receivers)} vs {n_groups}"
            )
            raise ValueError(msg)

    shot_dtype = np.dtype(
        [
            ("line_name", "U32"),
            ("shot_point", "i4"),
            ("easting", "f8"),
            ("northing", "f8"),
            ("water_depth", "f8"),
            ("day_of_year", "i4"),
            ("time_hhmmss", "U8"),
            ("time_ms", "i4"),
        ]
    )
    shot_table = np.zeros(len(shots), dtype=shot_dtype)
    receivers = np.zeros((len(shots), n_groups, 3), dtype=np.float64)

    for i, shot in enumerate(shots):
        src = shot.source
        shot_table[i] = (
            shot.line_name,
            shot.shot_point,
            src.easting,
            src.northing,
            src.water_depth,
            src.day_of_year,
            src.time_hhmmss,
            src.time_ms,
        )
        for j, recv in enumerate(shot.receivers):
            receivers[i, j, 0] = recv.easting
            receivers[i, j, 1] = recv.northing
            receivers[i, j, 2] = recv.depth

    return shot_table, receivers
