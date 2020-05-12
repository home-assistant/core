"""Errors for the Mikrotik component."""
from homeassistant.exceptions import HomeAssistantError


class MikrotikError(HomeAssistantError):
    """Base class for Mikrotik errors."""


class CannotConnect(MikrotikError):
    """Unable to connect to the hub."""


class LoginError(MikrotikError):
    """Component got logged out."""
