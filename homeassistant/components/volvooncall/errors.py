"""Exceptions specific to volvooncall."""
from homeassistant.exceptions import HomeAssistantError


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
