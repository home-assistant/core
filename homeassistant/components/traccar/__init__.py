"""Support for Traccar."""
import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.const import CONF_WEBHOOK_ID, HTTP_OK, HTTP_UNPROCESSABLE_ENTITY
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_ACCURACY,
    ATTR_ALTITUDE,
    ATTR_BATTERY,
    ATTR_BEARING,
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_SPEED,
    ATTR_TIMESTAMP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

TRACKER_UPDATE = f"{DOMAIN}_tracker_update"


DEFAULT_ACCURACY = HTTP_OK
DEFAULT_BATTERY = -1


def _id(value: str) -> str:
    """Coerce id by removing '-'."""
    return value.replace("-", "")


WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ID): vol.All(cv.string, _id),
        vol.Required(ATTR_LATITUDE): cv.latitude,
        vol.Required(ATTR_LONGITUDE): cv.longitude,
        vol.Optional(ATTR_ACCURACY, default=DEFAULT_ACCURACY): vol.Coerce(float),
        vol.Optional(ATTR_ALTITUDE): vol.Coerce(float),
        vol.Optional(ATTR_BATTERY, default=DEFAULT_BATTERY): vol.Coerce(float),
        vol.Optional(ATTR_BEARING): vol.Coerce(float),
        vol.Optional(ATTR_SPEED): vol.Coerce(float),
        vol.Optional(ATTR_TIMESTAMP): vol.Coerce(int),
    }
)


async def async_setup(hass, hass_config):
    """Set up the Traccar component."""
    hass.data[DOMAIN] = {"devices": set(), "unsub_device_tracker": {}}
    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook with Traccar request."""
    try:
        data = WEBHOOK_SCHEMA(dict(request.query))
    except vol.MultipleInvalid as error:
        return web.Response(text=error.error_message, status=HTTP_UNPROCESSABLE_ENTITY)

    attrs = {
        ATTR_ALTITUDE: data.get(ATTR_ALTITUDE),
        ATTR_BEARING: data.get(ATTR_BEARING),
        ATTR_SPEED: data.get(ATTR_SPEED),
    }

    device = data[ATTR_ID]

    async_dispatcher_send(
        hass,
        TRACKER_UPDATE,
        device,
        data[ATTR_LATITUDE],
        data[ATTR_LONGITUDE],
        data[ATTR_BATTERY],
        data[ATTR_ACCURACY],
        attrs,
    )

    return web.Response(text=f"Setting location for {device}", status=HTTP_OK)


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    hass.components.webhook.async_register(
        DOMAIN, "Traccar", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, DEVICE_TRACKER)
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])
    hass.data[DOMAIN]["unsub_device_tracker"].pop(entry.entry_id)()
    await hass.config_entries.async_forward_entry_unload(entry, DEVICE_TRACKER)
    return True


async_remove_entry = config_entry_flow.webhook_async_remove_entry
