"""The errors of Epson integration."""
from homeassistant import exceptions


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
