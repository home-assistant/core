"""Errors for the Sabnzbd component."""
from homeassistant.exceptions import HomeAssistantError


class AuthenticationError(HomeAssistantError):
    """Wrong Username or Password."""


class UnknownError(HomeAssistantError):
    """Unknown Error."""
