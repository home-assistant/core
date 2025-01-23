"""Utils for Lovelace."""

from homeassistant.exceptions import HomeAssistantError


class ConfigNotFound(HomeAssistantError):
    """When no config available."""
