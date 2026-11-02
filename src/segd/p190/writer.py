"""Write UKOOA P1/90 (P190) navigation files."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from segd.p190.schema import PointRecord
    from segd.p190.schema import ReceiverGroup
    from segd.p190.schema import ShotGather


def format_point_record(point: PointRecord) -> str:
    """Format a point record as an 86-character P190 line (no newline)."""
    # Prefer the original raw card when it is long enough to round-trip.
    if len(point.raw) >= 80 and point.raw[0] == point.record_type:
        return point.raw[:86]

    line_name = f"{point.line_name:<12}"[:12]
    body = (
        f"{point.record_type}{line_name}{point.point_index:>3}  "
        f"{point.point_number:05d}"
        f"{point.latitude_raw}{point.longitude_raw} "
        f"{point.easting:.1f}{point.northing:.1f}{point.water_depth:.1f}"
        f"{point.day_of_year:03d}{point.time_hhmmss}.{point.time_ms:03d}"
    )
    return f"{body:<86}"[:86]


def format_receiver_line(groups: Sequence[ReceiverGroup]) -> str:
    """Format up to three receiver groups into an 80-character R card."""
    if not 1 <= len(groups) <= 3:
        msg = "R cards must contain 1 to 3 receiver groups."
        raise ValueError(msg)

    parts = ["R"]
    for group in groups:
        parts.append(
            f"{group.group_number:4d} {group.easting:.1f}{group.northing:.1f}{group.depth:.1f}"
        )
    line = "".join(parts)
    return f"{line:<80}"[:80]


def format_shot_gather(shot: ShotGather) -> list[str]:
    """Format one shot gather as P190 lines (without newlines)."""
    lines: list[str] = []
    if shot.vessel is not None:
        lines.append(format_point_record(shot.vessel))
    if shot.echo is not None:
        lines.append(format_point_record(shot.echo))
    for antenna in shot.antennas:
        lines.append(format_point_record(antenna))
    lines.append(format_point_record(shot.source))
    if shot.gun is not None:
        lines.append(format_point_record(shot.gun))
    # Optional centre / tail buoy style records if present in original order
    # are stored as source-adjacent; include C if encoded on source.raw only.
    if shot.tail is not None:
        # Insert C-record placeholder only when we have a dedicated attribute later.
        lines.append(format_point_record(shot.tail))

    for i in range(0, len(shot.receivers), 3):
        chunk = shot.receivers[i : i + 3]
        lines.append(format_receiver_line(chunk))
    return lines


def render_p190(headers: Sequence[str], shots: Sequence[ShotGather]) -> str:
    """Render a full P190 text document."""
    out_lines = [h.rstrip("\n\r") for h in headers]
    for shot in shots:
        # Prefer original raw ordering when all point raws exist
        point_raws = []
        for point in (
            shot.vessel,
            shot.echo,
            *shot.antennas,
            shot.source,
            shot.gun,
            shot.tail,
        ):
            if point is not None:
                point_raws.append(format_point_record(point))
        out_lines.extend(point_raws)
        for i in range(0, len(shot.receivers), 3):
            out_lines.append(format_receiver_line(shot.receivers[i : i + 3]))
    return "\n".join(out_lines) + "\n"
