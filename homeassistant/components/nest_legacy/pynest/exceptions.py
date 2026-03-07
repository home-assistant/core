"""Exceptions used by PyNest."""


class PynestException(Exception):
    """Base class for all exceptions raised by pynest."""


class NestServiceException(PynestException):
    """Raised when service is not available."""


class BadCredentialsException(PynestException):
    """Raised when credentials are incorrect."""


class NotAuthenticatedException(PynestException):
    """Raised when session is invalid."""


class NonRetryablePynestException(PynestException):
    """Raised when an operation fails with a non-retryable error."""


class GatewayTimeoutException(NestServiceException):
    """Raised when server times out."""


class BadGatewayException(NestServiceException):
    """Raised when server returns Bad Gateway."""


class EmptyResponseException(NestServiceException):
    """Raised when server returns Status 200 (OK), but empty response."""
