"""
Support for the World Air Quality Index service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/waqi/
"""
import asyncio
import logging
from datetime import timedelta, timezone
from dateutil import parser as dt_parser

import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.const import (CONF_TOKEN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
        vol.Optional(CONF_STATIONS): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_LOCATIONS): vol.All(cv.ensure_list, [cv.string]),
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the WAQI component."""
    import waqiasync

    conf = config[DOMAIN]
    token = conf[CONF_TOKEN]
    station_filter = conf[CONF_STATIONS]
    locations = conf[CONF_LOCATIONS]

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
            asyncio.TimeoutError) as err:
        _LOGGER.error("Failed to connect to WAQI servers: %s", err)
        return False
    return True


class WaqiData:
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

    async def async_update(self):
        """Get the data from Waqi API."""
        if self.uid:
            result = await self._client.get_station_by_number(self.uid)
        elif self.url:
            result = await self._client.get_station_by_name(self.url)
        else:
            result = None
        self.data = result

    @property
    def attribution(self):
        """Return the attribution."""
        return [ATTRIBUTION] + [
            v['name'] for v in self.data.get('attributions', [])]

    @property
    def update_time(self):
        """Return the time of the data update."""
        if 'debug' in self.data and 'sync' in self.data['debug']:
            return dt_parser.parse(
                self.data['debug']['sync']).astimezone(timezone.utc)
        return None

    def get(self, key):
        """Extract the measurement value from API data."""
        if 'iaqi' in self.data and key in self.data['iaqi']:
            return self.data['iaqi'][key]['v']
        return None
