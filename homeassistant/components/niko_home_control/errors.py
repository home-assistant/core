from homeassistant import exceptions


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid host."""


class InvalidPort(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid port."""
