"""Errors for the UniFi Network integration."""

from homeassistant.exceptions import HomeAssistantError


class UnifiException(HomeAssistantError):
    """Base class for UniFi Network exceptions."""


class AlreadyConfigured(UnifiException):
    """Controller is already configured."""


class AuthenticationRequired(UnifiException):
    """Unknown error occurred."""


class CannotConnect(UnifiException):
    """Unable to connect to UniFi Network."""


class LoginRequired(UnifiException):
    """Integration got logged out."""


class UserLevel(UnifiException):
    """User level too low."""
