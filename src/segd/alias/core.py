"""Header key alias normalization."""

from __future__ import annotations

from rapidfuzz import process

from segd.exceptions import InvalidFieldError

# Common aliases → canonical MDIO / SEG-Y style names
_ALIASES: dict[str, str] = {
    "ffid": "orig_field_record_num",
    "field_record": "orig_field_record_num",
    "ep": "energy_source_point_num",
    "shot_point": "energy_source_point_num",
    "sp": "energy_source_point_num",
    "channel": "trace_num_orig_record",
    "trace_number": "trace_num_orig_record",
    "sx": "source_coord_x",
    "sy": "source_coord_y",
    "gx": "group_coord_x",
    "gy": "group_coord_y",
    "cdpx": "source_coord_x",
    "cdpy": "source_coord_y",
}


def normalize_key(key: str) -> str:
    """Normalize a header key to canonical form."""
    lowered = key.strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(lowered, lowered)


def validate_key(
    key: str, original_key: str, names: tuple[str, ...] | list[str]
) -> None:
    """Validate a header key exists, suggesting close matches on failure."""
    if key in names:
        return

    matches = process.extract(original_key, names, limit=3)
    suggestions = [match[0] for match in matches]
    while len(suggestions) < 3:
        suggestions.append(suggestions[-1] if suggestions else original_key)
    raise InvalidFieldError(original_key, suggestions)
