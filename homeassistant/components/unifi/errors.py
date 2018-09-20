"""Errors for the UniFi component."""
from homeassistant.exceptions import HomeAssistantError


class UnifiException(HomeAssistantError):
    """Base class for UniFi exceptions."""


class CannotConnect(UnifiException):
    """Unable to connect to the controller."""


class AuthenticationRequired(UnifiException):
    """Unknown error occurred."""


class UserLevel(UnifiException):
    """User level too low."""


class LoginRequired(UnifiException):
    """Component got logged out."""
