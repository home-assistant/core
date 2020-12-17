"""Nuki.io webhook handling."""
import logging

from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import DOMAIN
from .const import ATTR_DATA, ATTR_NUKI_ID

_LOGGER = logging.getLogger(__name__)


async def register_webhook(hass, config):
    """Register webhook handler."""
    webhook_register(hass, DOMAIN, "Nuki", config[CONF_WEBHOOK_ID], handle_webhook)

    async def cleanup(_):
        webhook_unregister(hass, config[CONF_WEBHOOK_ID])

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)


async def handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    try:
        data = await request.json()
    except ValueError as err:
        _LOGGER.error("Error in data: %s", err)
        return None

    _LOGGER.debug("Got webhook data: %s", data)

    nuki_id = data.get("nukiId")

    async_dispatcher_send(
        hass,
        f"signal-{DOMAIN}-webhook-{nuki_id}",
        {ATTR_NUKI_ID: nuki_id, ATTR_DATA: data},
    )
