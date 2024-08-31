"""nuki integration helpers."""
from homeassistant import exceptions


def parse_id(hardware_id):
    """Parse Nuki ID."""
    return hex(hardware_id).split("x")[-1].upper()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NukiWebhookException(exceptions.HomeAssistantError):
    """Error to indicate there was an issue with the webhook."""
