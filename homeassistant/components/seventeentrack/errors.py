"""Errors for the SeventeenTrack component."""
from homeassistant.exceptions import HomeAssistantError


class AuthenticationError(HomeAssistantError):
    """Wrong Username or Password."""
