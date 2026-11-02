"""SEG-D library exceptions."""


class SegdError(Exception):
    """Base class for all exceptions in this library."""


class SegdFileSpecMismatchError(SegdError):
    """Raised when file spec with parsed fields do not match file size or peers."""


class EndiannessInferenceError(SegdError):
    """Raised when endianness inference has failed."""


class UnsupportedFormatError(SegdError):
    """Raised when a SEG-D format code is not supported."""


class NavigationJoinError(SegdError):
    """Raised when P190 geometry cannot be joined to SEG-D traces."""


class InvalidFieldError(SegdError):
    """Raised when a header key does not match known values."""

    def __init__(self, key: str, suggestions: list[str]):
        self.key = key
        self.suggestions = suggestions
        msg = self._generate_message()
        super().__init__(msg)

    def _generate_message(self) -> str:
        """Generate custom user message."""
        first, second, third = self.suggestions
        suggestion_text = f"'{first}', '{second}', or '{third}'"
        return f"Invalid key '{self.key}'. Did you mean one of: {suggestion_text}?"


class NonSpecFieldError(SegdError):
    """Raised when a header field is missing from a HeaderArray."""
