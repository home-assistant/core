"""Errors for the Transmission component."""
from homeassistant.exceptions import HomeAssistantError


class AuthenticationError(HomeAssistantError):
    """Wrong Username or Password."""


class CannotConnect(HomeAssistantError):
    """Unable to connect to client."""


class UnknownError(HomeAssistantError):
    """Unknown Error."""
