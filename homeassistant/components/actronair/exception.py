"""Exception classes in one file."""


class ConversionException(Exception):
    """Raised when data conversion errors occur."""


class FailedToRefreshToken(Exception):
    """Raised when refreshing the token fails."""
