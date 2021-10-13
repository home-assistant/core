"""The lookin integration exceptions."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

__all__ = (
    "NoUsableService",
    "DeviceNotFound",
    "DeviceAlreadyConfigured",
)


class NoUsableService(HomeAssistantError):
    """Error to indicate device could not be found."""


class DeviceNotFound(HomeAssistantError):
    """Error to indicate device could not be found."""


class DeviceAlreadyConfigured(HomeAssistantError):
    """Error to indicate device is already configured."""
