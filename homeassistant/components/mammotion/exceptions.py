"""Exceptions for the Mammotion integration."""

from homeassistant.exceptions import HomeAssistantError


class CommandFailedError(HomeAssistantError):
    """Error to indicate a command was not carried out by the device."""
