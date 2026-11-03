"""SEG-D file metadata shaped like MDIO's ``SegyFileInfo``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict

from segd.accessors import COORD_SCALAR
from segd.file import SegdFile

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy as np
    from numpy.typing import NDArray

    from segd.config import SegdFileSettings
    from segd.config import SegdHeaderOverrides
    from segd.schema import SegdSpec


class SegdFileArguments(TypedDict, total=False):
    """Pickleable kwargs for opening :class:`~segd.file.SegdFile` in workers."""

    url: str | Sequence[str]
    spec: SegdSpec | None
    settings: SegdFileSettings | None
    header_overrides: SegdHeaderOverrides | None
    navigation: str | None
    cable: int
    gun: int
    sail_line_map: dict[str, int] | None


@dataclass
class SegdFileInfo:
    """SEG-D summary metadata used by the MDIO ingest stages."""

    num_traces: int
    sample_labels: NDArray[np.int32]
    text_header: str
    binary_header_dict: dict[str, Any]
    raw_binary_headers: bytes
    coordinate_scalar: int
    p190_path: str | None = None
    urls: tuple[str, ...] = ()


def get_segd_file_info(segd_file_kwargs: SegdFileArguments) -> SegdFileInfo:
    """Open a temporary :class:`~segd.file.SegdFile` and collect metadata."""
    sf = SegdFile(
        url=segd_file_kwargs["url"],
        spec=segd_file_kwargs.get("spec"),
        settings=segd_file_kwargs.get("settings"),
        header_overrides=segd_file_kwargs.get("header_overrides"),
        navigation=segd_file_kwargs.get("navigation"),
        cable=segd_file_kwargs.get("cable", 1),
        gun=segd_file_kwargs.get("gun", 1),
        sail_line_map=segd_file_kwargs.get("sail_line_map"),
    )
    return SegdFileInfo(
        num_traces=sf.num_traces,
        sample_labels=sf.sample_labels.copy(),
        text_header=sf.text_header,
        binary_header_dict=sf.binary_header.to_dict(),
        raw_binary_headers=b"",
        coordinate_scalar=int(COORD_SCALAR),
        p190_path=segd_file_kwargs.get("navigation"),
        urls=tuple(sf.urls),
    )
