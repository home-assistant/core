"""Errors for the Livebox component."""
from homeassistant.exceptions import HomeAssistantError


class LiveboxException(HomeAssistantError):
    """Base class for Livebox exceptions."""


class CannotConnect(LiveboxException):
    """Unable to connect to the bridge."""


class AuthenticationRequired(LiveboxException):
    """Unknown error occurred."""
