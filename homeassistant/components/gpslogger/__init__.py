"""Support for GPSLogger."""
import logging

import voluptuous as vol
from aiohttp import web

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import ATTR_BATTERY
from homeassistant.const import HTTP_UNPROCESSABLE_ENTITY, \
    HTTP_OK, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_WEBHOOK_ID
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'gpslogger'
TRACKER_UPDATE = '{}_tracker_update'.format(DOMAIN)

ATTR_ALTITUDE = 'altitude'
ATTR_ACCURACY = 'accuracy'
ATTR_ACTIVITY = 'activity'
ATTR_DEVICE = 'device'
ATTR_DIRECTION = 'direction'
ATTR_PROVIDER = 'provider'
ATTR_SPEED = 'speed'

DEFAULT_ACCURACY = 200
DEFAULT_BATTERY = -1


def _id(value: str) -> str:
    """Coerce id by removing '-'."""
    return value.replace('-', '')


WEBHOOK_SCHEMA = vol.Schema({
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
})


async def async_setup(hass, hass_config):
    """Set up the GPSLogger component."""
    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook with GPSLogger request."""
    try:
        data = WEBHOOK_SCHEMA(dict(await request.post()))
    except vol.MultipleInvalid as error:
        return web.Response(
            text=error.error_message,
            status=HTTP_UNPROCESSABLE_ENTITY
        )

    attrs = {
        ATTR_SPEED: data.get(ATTR_SPEED),
        ATTR_DIRECTION: data.get(ATTR_DIRECTION),
        ATTR_ALTITUDE: data.get(ATTR_ALTITUDE),
        ATTR_PROVIDER: data.get(ATTR_PROVIDER),
        ATTR_ACTIVITY: data.get(ATTR_ACTIVITY)
    }

    device = data[ATTR_DEVICE]

    async_dispatcher_send(
        hass, TRACKER_UPDATE, device,
        (data[ATTR_LATITUDE], data[ATTR_LONGITUDE]),
        data[ATTR_BATTERY], data[ATTR_ACCURACY], attrs)

    return web.Response(
        text='Setting location for {}'.format(device),
        status=HTTP_OK
    )


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    hass.components.webhook.async_register(
        DOMAIN, 'GPSLogger', entry.data[CONF_WEBHOOK_ID], handle_webhook)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, DEVICE_TRACKER)
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])

    await hass.config_entries.async_forward_entry_unload(entry, DEVICE_TRACKER)
    return True


# pylint: disable=invalid-name
async_remove_entry = config_entry_flow.webhook_async_remove_entry


config_entry_flow.register_webhook_flow(
    DOMAIN,
    'GPSLogger Webhook',
    {
        'docs_url': 'https://www.home-assistant.io/components/gpslogger/'
    }
)
