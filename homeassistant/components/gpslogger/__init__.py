"""Support for GPSLogger."""
import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components.device_tracker import (
    ATTR_BATTERY,
    DOMAIN as DEVICE_TRACKER,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_WEBHOOK_ID,
    HTTP_OK,
    HTTP_UNPROCESSABLE_ENTITY,
)
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_ACCURACY,
    ATTR_ACTIVITY,
    ATTR_ALTITUDE,
    ATTR_DEVICE,
    ATTR_DIRECTION,
    ATTR_PROVIDER,
    ATTR_SPEED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

TRACKER_UPDATE = f"{DOMAIN}_tracker_update"


DEFAULT_ACCURACY = 200
DEFAULT_BATTERY = -1


def _id(value: str) -> str:
    """Coerce id by removing '-'."""
    return value.replace("-", "")


WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE): _id,
        vol.Required(ATTR_LATITUDE): cv.latitude,
        vol.Required(ATTR_LONGITUDE): cv.longitude,
        vol.Optional(ATTR_ACCURACY, default=DEFAULT_ACCURACY): vol.Coerce(float),
        vol.Optional(ATTR_ACTIVITY): cv.string,
        vol.Optional(ATTR_ALTITUDE): vol.Coerce(float),
        vol.Optional(ATTR_BATTERY, default=DEFAULT_BATTERY): vol.Coerce(float),
        vol.Optional(ATTR_DIRECTION): vol.Coerce(float),
        vol.Optional(ATTR_PROVIDER): cv.string,
        vol.Optional(ATTR_SPEED): vol.Coerce(float),
    }
)


async def async_setup(hass, hass_config):
    """Set up the GPSLogger component."""
    hass.data[DOMAIN] = {"devices": set(), "unsub_device_tracker": {}}
    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook with GPSLogger request."""
    try:
        data = WEBHOOK_SCHEMA(dict(await request.post()))
    except vol.MultipleInvalid as error:
        return web.Response(text=error.error_message, status=HTTP_UNPROCESSABLE_ENTITY)

    attrs = {
        ATTR_SPEED: data.get(ATTR_SPEED),
        ATTR_DIRECTION: data.get(ATTR_DIRECTION),
        ATTR_ALTITUDE: data.get(ATTR_ALTITUDE),
        ATTR_PROVIDER: data.get(ATTR_PROVIDER),
        ATTR_ACTIVITY: data.get(ATTR_ACTIVITY),
    }

    device = data[ATTR_DEVICE]

    async_dispatcher_send(
        hass,
        TRACKER_UPDATE,
        device,
        (data[ATTR_LATITUDE], data[ATTR_LONGITUDE]),
        data[ATTR_BATTERY],
        data[ATTR_ACCURACY],
        attrs,
    )

    return web.Response(text=f"Setting location for {device}", status=HTTP_OK)


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    hass.components.webhook.async_register(
        DOMAIN, "GPSLogger", entry.data[CONF_WEBHOOK_ID], handle_webhook
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


# pylint: disable=invalid-name
async_remove_entry = config_entry_flow.webhook_async_remove_entry
