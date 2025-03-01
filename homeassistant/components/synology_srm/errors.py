"""Errors for the Synology SRM component."""

from homeassistant.exceptions import HomeAssistantError


class CannotConnect(HomeAssistantError):
    """Unable to connect to the hub."""


class LoginError(HomeAssistantError):
    """Component got logged out."""
