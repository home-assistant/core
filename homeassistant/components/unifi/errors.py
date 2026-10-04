"""Errors for the UniFi Network integration."""

import aiounifi

from homeassistant.exceptions import HomeAssistantError


def controller_error_reason(err: aiounifi.AiounifiException) -> str:
    """Return the controller message code or a short reason, never the raw payload."""
    try:
        msg = err.args[0]["meta"]["msg"]
    except IndexError, KeyError, TypeError:
        msg = err.args[0] if err.args else None
    return msg if isinstance(msg, str) else type(err).__name__


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
