"""Exceptions for the Remootio integration."""
from homeassistant.exceptions import HomeAssistantError


class UnsupportedRemootioDeviceError(HomeAssistantError):
    """Error to indicate unsupported Remootio device."""


class UnsupportedRemootioApiVersionError(UnsupportedRemootioDeviceError):
    """Error to indicate unsupported Remootio API version."""


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
