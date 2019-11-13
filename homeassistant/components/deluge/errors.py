"""Errors for the Deluge component."""
from homeassistant.exceptions import HomeAssistantError


class UserNameError(HomeAssistantError):
    """Wrong Username."""


class PasswordError(HomeAssistantError):
    """Wrong Password."""


class CannotConnect(HomeAssistantError):
    """Unable to connect to client."""


class UnknownError(HomeAssistantError):
    """Unknown error occured."""
