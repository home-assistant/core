"""Device exceptions."""
from homeassistant.exceptions import HomeAssistantError


class InvalidDevice(HomeAssistantError):
    """When device is invalid."""


class DeviceNotFound(HomeAssistantError):
    """When referenced device not found."""
