"""Exceptions specific to volvooncall."""


class InvalidRegionError(Exception):
    """Raised when the input region is unexpected."""


class AuthenticationError(Exception):
    """Raised when the input credentials are invalid."""
