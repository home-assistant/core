"""
Support for Traccar device tracking.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.traccar/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL,
    CONF_PASSWORD, CONF_USERNAME, ATTR_BATTERY_LEVEL)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import slugify


REQUIREMENTS = ['pytraccar==0.2.0']

_LOGGER = logging.getLogger(__name__)

ATTR_ADDRESS = 'address'
ATTR_CATEGORY = 'category'
ATTR_GEOFENCE = 'geofence'
ATTR_MOTION = 'motion'
ATTR_SPEED = 'speed'
ATTR_TRACKER = 'tracker'

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=8082): cv.port,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
})


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return a Traccar scanner."""
    from pytraccar.api import API

    session = async_get_clientsession(hass, config[CONF_VERIFY_SSL])

    api = API(hass.loop, session, config[CONF_USERNAME], config[CONF_PASSWORD],
              config[CONF_HOST], config[CONF_PORT], config[CONF_SSL])
    scanner = TraccarScanner(api, hass, async_see)
    return await scanner.async_init()


class TraccarScanner:
    """Define an object to retrieve Traccar data."""

    def __init__(self, api, hass, async_see):
        """Initialize."""
        self._async_see = async_see
        self._api = api
        self._hass = hass

    async def async_init(self):
        """Further initialize connection to Traccar."""
        await self._api.test_connection()
        if self._api.authenticated:
            await self._async_update()
            async_track_time_interval(self._hass,
                                      self._async_update,
                                      DEFAULT_SCAN_INTERVAL)

        return self._api.authenticated

    async def _async_update(self, now=None):
        """Update info from Traccar."""
        _LOGGER.debug('Updating device data.')
        await self._api.get_device_info()
        for devicename in self._api.device_info:
            device = self._api.device_info[devicename]
            attr = {}
            attr[ATTR_TRACKER] = 'traccar'
            if device.get('address') is not None:
                attr[ATTR_ADDRESS] = device['address']
            if device.get('geofence') is not None:
                attr[ATTR_GEOFENCE] = device['geofence']
            if device.get('category') is not None:
                attr[ATTR_CATEGORY] = device['category']
            if device.get('speed') is not None:
                attr[ATTR_SPEED] = device['speed']
            if device.get('battery') is not None:
                attr[ATTR_BATTERY_LEVEL] = device['battery']
            if device.get('motion') is not None:
                attr[ATTR_MOTION] = device['motion']
            await self._async_see(
                dev_id=slugify(device['device_id']),
                gps=(device.get('latitude'), device.get('longitude')),
                attributes=attr)
