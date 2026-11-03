"""Join RAW record catalog entries to P190 shots."""

from __future__ import annotations

from typing import TYPE_CHECKING

from segd.exceptions import NavigationJoinError

if TYPE_CHECKING:
    from segd.catalog import RecordCatalog
    from segd.p190.file import P190File


def join_catalog_to_p190(
    catalog: RecordCatalog, navigation: P190File
) -> dict[int, int]:
    """Match each catalog record to a P190 shot by ``shot_point``.

    Args:
        catalog: Light-weight RAW record catalog.
        navigation: Opened P190 navigation file.

    Returns:
        Mapping of catalog record index → P190 shot gather index.

    Raises:
        NavigationJoinError: If a RAW shot is missing from P190, a P190 shot has no
            matching RAW (when counts differ for the overlapping set), or receiver
            counts disagree.
    """
    p190_by_shot: dict[int, int] = {}
    for i, gather in enumerate(navigation.shot_gathers):
        if gather.shot_point in p190_by_shot:
            msg = f"Duplicate shot_point {gather.shot_point} in P190 navigation."
            raise NavigationJoinError(msg)
        p190_by_shot[gather.shot_point] = i

    mapping: dict[int, int] = {}
    for record_index, record in enumerate(catalog.records):
        shot_point = record.info.shot_point
        if shot_point is None:
            msg = f"Record {record.url} has no shot_point in general headers."
            raise NavigationJoinError(msg)
        if shot_point not in p190_by_shot:
            msg = (
                f"Shot point {shot_point} from record {record.url} "
                "not found in P190 navigation."
            )
            raise NavigationJoinError(msg)

        gather = navigation.shot_gathers[p190_by_shot[shot_point]]
        if len(gather.receivers) != record.info.channels:
            msg = (
                f"P190 shot {shot_point} has {len(gather.receivers)} receivers "
                f"but SEG-D record {record.url} has {record.info.channels} channels."
            )
            raise NavigationJoinError(msg)

        # Optional time consistency check when both sides expose Julian day + HMS.
        gh_doy = record.info.day_of_year
        p190_doy = gather.source.day_of_year
        if gh_doy and p190_doy and gh_doy != p190_doy:
            msg = (
                f"Day-of-year mismatch for shot {shot_point}: "
                f"SEG-D={gh_doy}, P190={p190_doy}."
            )
            raise NavigationJoinError(msg)

        mapping[record_index] = p190_by_shot[shot_point]

    return mapping
