"""
Support for the World Air Quality Index service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/waqi/
"""
import asyncio
import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol

from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.const import (CONF_TOKEN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['waqiasync==1.0.0']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Data provided by the World Air Quality Index project'

CONF_LOCATIONS = 'locations'
CONF_STATIONS = 'stations'

DOMAIN = 'waqi'

SCAN_INTERVAL = timedelta(minutes=5)

TIMEOUT = 10

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_STATIONS): cv.ensure_list,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_LOCATIONS): cv.ensure_list
    })
})


async def async_setup(hass, config):
    """Set up the WAQI component."""
    import waqiasync

    conf = config.get(DOMAIN)
    token = conf.get(CONF_TOKEN)
    station_filter = conf.get(CONF_STATIONS)
    locations = conf.get(CONF_LOCATIONS)

    client = waqiasync.WaqiClient(
        token, async_get_clientsession(hass), timeout=TIMEOUT)

    try:
        for location_name in locations:
            stations = await client.search(location_name)
            _LOGGER.debug("The following stations were returned: %s", stations)
            for station in stations:
                waqi_data = WaqiData(client, station)
                if not station_filter or \
                    {waqi_data.uid,
                     waqi_data.url,
                     waqi_data.station_name} & set(station_filter):
                    await waqi_data.async_update()
                    hass.async_create_task(async_load_platform(
                        hass, 'air_quality', DOMAIN, {'data': waqi_data},
                        config))
                    hass.async_create_task(async_load_platform(
                        hass, 'sensor', DOMAIN, {'data': waqi_data}, config))
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError):
        _LOGGER.exception('Failed to connect to WAQI servers.')
        raise PlatformNotReady
    return True


class WaqiData(Entity):
    """Get data from WAQI API."""

    def __init__(self, client, station):
        """Initialize the data object."""
        self._client = client
        self.station = station

        try:
            self.uid = station['uid']
        except (KeyError, TypeError):
            self.uid = None
        try:
            self.url = station['station']['url']
        except (KeyError, TypeError):
            self.url = None
        try:
            self.station_name = station['station']['name']
        except (KeyError, TypeError):
            self.station_name = None

        self.data = {}

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the data from Waqi API."""
        if self.uid:
            result = await self._client.get_station_by_number(self.uid)
        elif self.url:
            result = await self._client.get_station_by_name(self.url)
        self.data = result

    @property
    def attribution(self):
        """Return the attribution."""
        return [ATTRIBUTION] + [
            v['name'] for v in self.data.get('attributions', [])]

    def get(self, key):
        """Extract the measurement value from API data."""
        if 'iaqi' in self.data and key in self.data['iaqi']:
            return self.data['iaqi'][key]['v']
        return None
