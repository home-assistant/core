"""Exceptions."""

from typing import override

from homeassistant.exceptions import HomeAssistantError


class VisonicException(HomeAssistantError):
    """Custom exception for library errors, with optional error code and original exception."""

    def __init__(
        self,
        message: str,
        code: int | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message (str): Descriptive error message.
            code (int | None): Optional error code for context.
            original_exception (Exception | None): Optional original exception to wrap.
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.original_exception = original_exception

    @override
    def __str__(self) -> str:
        """Return a readable string representation of the exception."""
        base_msg = (
            f"[Error {self.code}] {self.message}"
            if self.code is not None
            else self.message
        )
        if self.original_exception:
            oe = repr(self.original_exception)
            return f"{base_msg} (caused by {oe})"
        return base_msg


class VisonicAuthException(VisonicException):
    """Authorisation Exception."""
