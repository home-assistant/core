"""Exceptions for the Reolink Camera integration."""
from homeassistant.exceptions import HomeAssistantError


class UserNotAdmin(HomeAssistantError):
    """Raised when user is not admin."""
