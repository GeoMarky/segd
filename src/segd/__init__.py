"""Python SEG-D and UKOOA P1/90 I/O."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

from segd.factory import SegdFactory
from segd.file import SegdFile

try:
    __version__ = version("segd")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["SegdFile", "SegdFactory", "__version__"]
