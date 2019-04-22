"""Support for Geofency."""
import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.const import (
    ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_NAME, CONF_WEBHOOK_ID, HTTP_OK,
    HTTP_UNPROCESSABLE_ENTITY, STATE_NOT_HOME)
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'geofency'
CONF_MOBILE_BEACONS = 'mobile_beacons'

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Optional(CONF_MOBILE_BEACONS, default=[]): vol.All(
            cv.ensure_list, [cv.string]),
    }),
}, extra=vol.ALLOW_EXTRA)

ATTR_ADDRESS = 'address'
ATTR_BEACON_ID = 'beaconUUID'
ATTR_CURRENT_LATITUDE = 'currentLatitude'
ATTR_CURRENT_LONGITUDE = 'currentLongitude'
ATTR_DEVICE = 'device'
ATTR_ENTRY = 'entry'

BEACON_DEV_PREFIX = 'beacon'

LOCATION_ENTRY = '1'
LOCATION_EXIT = '0'

TRACKER_UPDATE = '{}_tracker_update'.format(DOMAIN)


def _address(value: str) -> str:
    r"""Coerce address by replacing '\n' with ' '."""
    return value.replace('\n', ' ')


WEBHOOK_SCHEMA = vol.Schema({
    vol.Required(ATTR_ADDRESS): vol.All(cv.string, _address),
    vol.Required(ATTR_DEVICE): vol.All(cv.string, slugify),
    vol.Required(ATTR_ENTRY): vol.Any(LOCATION_ENTRY, LOCATION_EXIT),
    vol.Required(ATTR_LATITUDE): cv.latitude,
    vol.Required(ATTR_LONGITUDE): cv.longitude,
    vol.Required(ATTR_NAME): vol.All(cv.string, slugify),
    vol.Optional(ATTR_CURRENT_LATITUDE): cv.latitude,
    vol.Optional(ATTR_CURRENT_LONGITUDE): cv.longitude,
    vol.Optional(ATTR_BEACON_ID): cv.string,
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, hass_config):
    """Set up the Geofency component."""
    config = hass_config.get(DOMAIN, {})
    mobile_beacons = config.get(CONF_MOBILE_BEACONS, [])
    hass.data[DOMAIN] = [slugify(beacon) for beacon in mobile_beacons]
    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook from Geofency."""
    try:
        data = WEBHOOK_SCHEMA(dict(await request.post()))
    except vol.MultipleInvalid as error:
        return web.Response(
            body=error.error_message,
            status=HTTP_UNPROCESSABLE_ENTITY
        )

    if _is_mobile_beacon(data, hass.data[DOMAIN]):
        return _set_location(hass, data, None)
    if data['entry'] == LOCATION_ENTRY:
        location_name = data['name']
    else:
        location_name = STATE_NOT_HOME
        if ATTR_CURRENT_LATITUDE in data:
            data[ATTR_LATITUDE] = data[ATTR_CURRENT_LATITUDE]
            data[ATTR_LONGITUDE] = data[ATTR_CURRENT_LONGITUDE]

    return _set_location(hass, data, location_name)


def _is_mobile_beacon(data, mobile_beacons):
    """Check if we have a mobile beacon."""
    return ATTR_BEACON_ID in data and data['name'] in mobile_beacons


def _device_name(data):
    """Return name of device tracker."""
    if ATTR_BEACON_ID in data:
        return "{}_{}".format(BEACON_DEV_PREFIX, data['name'])
    return data['device']


def _set_location(hass, data, location_name):
    """Fire HA event to set location."""
    device = _device_name(data)

    async_dispatcher_send(
        hass, TRACKER_UPDATE, device,
        (data[ATTR_LATITUDE], data[ATTR_LONGITUDE]), location_name, data)

    return web.Response(
        text="Setting location for {}".format(device), status=HTTP_OK)


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    hass.components.webhook.async_register(
        DOMAIN, 'Geofency', entry.data[CONF_WEBHOOK_ID], handle_webhook)

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
    'Geofency Webhook',
    {
        'docs_url': 'https://www.home-assistant.io/components/geofency/'
    }
)
