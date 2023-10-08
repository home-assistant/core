"""Exception set for LoRaWAN integration."""
from homeassistant.exceptions import HomeAssistantError


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class DeviceEuiNotFound(HomeAssistantError):
    """Error to indicate that the device is not found in TTN application."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidDeviceEui(HomeAssistantError):
    """Error to indicate a malformed device EUI."""
