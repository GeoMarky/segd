"""Transforms to apply to arrays and structured arrays."""

from __future__ import annotations

import logging
import sys
from abc import abstractmethod
from typing import TYPE_CHECKING

from segd.schema.base import Endianness

if TYPE_CHECKING:
    from typing import Any

    from numpy.typing import NDArray


logger = logging.getLogger(__name__)


def get_endianness(data: NDArray[Any]) -> Endianness:
    """Map the numpy byte order character to Endianness."""
    if data.dtype.isnative:
        return Endianness[sys.byteorder.upper()]

    return Endianness.LITTLE if data.dtype.byteorder == "<" else Endianness.BIG


class Transform:
    """Base class for header transformation strategies."""

    def __init__(self, keys: list[str] | None = None, copy: bool = False) -> None:
        self.keys = keys
        self.copy = copy
        logger.debug("Initialized %s.", self.__class__.__name__)

    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        """Applies transformation based on ndarray or struct array."""
        if self.copy:
            data = data.copy()

        if data.dtype.names is None:
            return self.transform(data)

        keys = self.keys or list(data.dtype.names)
        for key in keys:
            if key not in data.dtype.names:
                continue
            data[key] = self.transform(data[key])

        return data

    @abstractmethod
    def transform(self, data: NDArray[Any]) -> NDArray[Any]:
        """Transform implementation for transformation."""


class ByteSwapTransform(Transform):
    """Transform to swap endianness."""

    def transform(self, data: NDArray[Any]) -> NDArray[Any]:
        """Swap byte order."""
        return data.byteswap().view(data.dtype.newbyteorder())


class ScaleTransform(Transform):
    """Scale numeric fields by a constant."""

    def __init__(
        self,
        scale: float,
        keys: list[str] | None = None,
        copy: bool = False,
    ) -> None:
        super().__init__(keys=keys, copy=copy)
        self.scale = scale

    def transform(self, data: NDArray[Any]) -> NDArray[Any]:
        """Multiply by scale."""
        return data * self.scale


class TransformPipeline:
    """Pipeline of transforms applied in order."""

    def __init__(self) -> None:
        self.transforms: list[Transform] = []

    def add(self, transform: Transform) -> None:
        """Append a transform."""
        self.transforms.append(transform)

    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        """Apply all transforms sequentially."""
        for transform in self.transforms:
            data = transform.apply(data)
        return data


class TransformFactory:
    """Factory to build named transforms."""

    _registry: dict[str, type[Transform]] = {
        "byte_swap": ByteSwapTransform,
        "scale": ScaleTransform,
    }

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> Transform:  # noqa: ANN401
        """Create a transform by name."""
        try:
            transform_cls = cls._registry[name]
        except KeyError as err:
            msg = f"Unknown transform '{name}'."
            raise KeyError(msg) from err
        return transform_cls(**kwargs)
