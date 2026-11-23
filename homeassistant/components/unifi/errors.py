"""Errors for the UniFi Network integration."""

from homeassistant.exceptions import HomeAssistantError


class UnifiException(HomeAssistantError):
    """Base class for UniFi Network exceptions."""


class AlreadyConfigured(UnifiException):
    """Controller is already configured."""


class AuthenticationRequired(UnifiException):
    """Unknown error occurred."""


class MfaRequired(AuthenticationRequired):
    """Account requires multi-factor authentication, which is not supported."""


class CannotConnect(UnifiException):
    """Unable to connect to UniFi Network."""


class NetworkApiUnavailable(CannotConnect):
    """The console does not offer the UniFi Network Integration API."""


class LoginRequired(UnifiException):
    """Integration got logged out."""


class UserLevel(UnifiException):
    """User level too low."""
