"""Errors for the blebox component."""
from homeassistant.exceptions import HomeAssistantError


class BleBoxException(HomeAssistantError):
    """Base class for blebox exceptions."""


class CannotConnect(BleBoxException):
    """Unable to connect to the device."""


class UnsupportedVersion(BleBoxException):
    """Device has outdated firmware."""


class InvalidAuth(BleBoxException):
    """Error to indicate there is invalid auth."""
