"""P190 file reader and factory."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from fsspec.core import url_to_fs

from segd.p190.parser import parse_p190_lines
from segd.p190.parser import shots_to_tables
from segd.p190.writer import render_p190

if TYPE_CHECKING:
    from collections.abc import Sequence

    from segd.p190.schema import ShotGather


class P190File:
    """Read a UKOOA P1/90 navigation file."""

    def __init__(
        self,
        url: str,
        settings: dict[str, Any] | None = None,
    ) -> None:
        storage_options = (settings or {}).get("storage_options", {})
        self.fs, self.url = url_to_fs(url, **storage_options)
        with self.fs.open(self.url, mode="rt") as handle:
            lines = handle.readlines()
        self.header_cards, self._shots = parse_p190_lines(lines)
        self.shots, self.receivers = shots_to_tables(self._shots)

    @property
    def shot_gathers(self) -> list[ShotGather]:
        """List of parsed shot gathers."""
        return self._shots

    def shot_by_point(self, shot_point: int) -> ShotGather:
        """Lookup a shot gather by shot point number."""
        for shot in self._shots:
            if shot.shot_point == shot_point:
                return shot
        msg = f"Shot point {shot_point} not found in P190."
        raise KeyError(msg)

    @property
    def num_shots(self) -> int:
        """Number of shots."""
        return len(self._shots)

    @property
    def num_groups(self) -> int:
        """Receiver groups per shot."""
        if self.receivers.size == 0:
            return 0
        return int(self.receivers.shape[1])


class P190Factory:
    """Build P190 text from header cards and shot gathers."""

    def __init__(
        self,
        headers: Sequence[str] | None = None,
    ) -> None:
        self.headers = list(headers or [])

    def create(
        self,
        shots: Sequence[ShotGather],
    ) -> str:
        """Create a full P190 document string."""
        return render_p190(self.headers, shots)

    def to_file(
        self,
        url: str,
        shots: Sequence[ShotGather],
        **storage_options: Any,  # noqa: ANN401
    ) -> None:
        """Write P190 text to a URL via fsspec."""
        text = self.create(shots)
        fs, path = url_to_fs(url, **storage_options)
        with fs.open(path, mode="wt") as handle:
            handle.write(text)
