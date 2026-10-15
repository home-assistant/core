"""Errors for the cert_expiry integration."""

from homeassistant.exceptions import HomeAssistantError


class CertExpiryException(HomeAssistantError):
    """Base class for cert_expiry exceptions."""


class TemporaryFailure(CertExpiryException):
    """Temporary failure has occurred."""


class ValidationFailure(CertExpiryException):
    """Certificate validation failure has occurred."""


class InvalidCACertificate(CertExpiryException):
    """Additional trusted certificates are malformed."""


class ResolveFailed(TemporaryFailure):
    """Name resolution failed."""


class ConnectionTimeout(TemporaryFailure):
    """Network connection timed out."""


class ConnectionRefused(TemporaryFailure):
    """Network connection refused."""


class ConnectionReset(TemporaryFailure):
    """Network connection reset."""
