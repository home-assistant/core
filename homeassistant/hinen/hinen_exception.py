"""Hinen Exceptions."""

__all__ = [
    "DeprecatedError",
    "ForbiddenError",
    "HinenAPIError",
    "HinenAuthorizationError",
    "HinenBackendError",
    "HinenResourceNotFoundError",
    "InvalidRefreshTokenError",
    "InvalidTokenError",
    "MissingAppSecretError",
    "UnauthorizedError",
]


class HinenAPIError(Exception):
    """Base YouTube API exception."""


class HinenAuthorizationError(HinenAPIError):
    """Exception in the YouTube Authorization."""


class InvalidRefreshTokenError(HinenAPIError):
    """used User Refresh Token is invalid."""


class InvalidTokenError(HinenAPIError):
    """Used if an invalid token is set for the client."""


class UnauthorizedError(HinenAuthorizationError):
    """Not authorized to use this."""


class HinenBackendError(HinenAPIError):
    """When the YouTube API itself is down."""


class PartMissingError(HinenAPIError):
    """If you request a part which is not requested."""


class MissingAppSecretError(HinenAPIError):
    """When the app secret is not set but app authorization is attempted."""


class DeprecatedError(HinenAPIError):
    """If something has been marked as deprecated by the YouTube API."""


class HinenResourceNotFoundError(HinenAPIError):
    """If a requested resource was not found."""


class ForbiddenError(HinenAPIError):
    """If you are not allowed to do that."""
