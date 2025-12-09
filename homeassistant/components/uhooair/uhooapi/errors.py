"""Define package errors."""


class UhooError(Exception):
    """Base class for all Uhoo-related errors."""

    def __init__(self, message: str | None = None) -> None:
        """Initialize UhooError."""
        super().__init__(message or "An unknown Uhoo error occurred.")
        self.message = message

    def __str__(self) -> str:
        """Return message."""
        return self.message or super().__str__()


class RequestError(UhooError):
    """Error related to invalid requests."""

    def __init__(self, message: str, status: int | None = None) -> None:
        """Initialize RequestError."""
        super().__init__(message)
        self.status = status


class UnauthorizedError(UhooError):
    """Error for 401 Unauthorized responses."""

    def __init__(
        self, message: str = "Unauthorized (401): Invalid API key or token."
    ) -> None:
        """Initialize UnauthorizedError."""
        super().__init__(message)


class ForbiddenError(UhooError):
    """Error for 403 Forbidden responses."""

    def __init__(self, message: str = "Forbidden (403): Access denied.") -> None:
        """Initialize UnauthorizedError."""
        super().__init__(message)
