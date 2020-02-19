"""Errors for the cert_expiry integration."""
from homeassistant.exceptions import HomeAssistantError


class CertExpiryException(HomeAssistantError):
    """Base class for cert_expiry exceptions."""


class TemporaryFailure(CertExpiryException):
    """Temporary failure has occurred."""


class PermanentFailure(CertExpiryException):
    """Permanent failure has occurred."""
