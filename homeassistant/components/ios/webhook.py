"""Webhook handlers for mobile_app."""
from homeassistant.const import HTTP_NOT_FOUND
from homeassistant.util.decorator import Registry

from .const import CONF, DOMAIN
from .helpers import empty_okay_response, webhook_response

WEBHOOK_COMMANDS = Registry()


@WEBHOOK_COMMANDS.register("get_ios_config")
async def webhook_get_ios_config(hass, config_entry, data):
    """Handle a get mobile app specific config webhook."""
    resp = hass.data[DOMAIN][CONF]

    if resp:
        return webhook_response(resp, registration=config_entry.data)

    return empty_okay_response(status=HTTP_NOT_FOUND)
