"""
Support for the World Air Quality Index service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.waqi/
"""
import asyncio
import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol

from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_TIME, ATTR_TEMPERATURE, CONF_TOKEN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.components.air_pollutants import AirPollutantsEntity

REQUIREMENTS = ['waqiasync==1.0.0']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Data provided by the World Air Quality Index project'

CONF_LOCATIONS = 'locations'
CONF_STATIONS = 'stations'

SCAN_INTERVAL = timedelta(minutes=5)

TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_STATIONS): cv.ensure_list,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_LOCATIONS): cv.ensure_list,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the requested World Air Quality Index locations."""
    import waqiasync

    token = config.get(CONF_TOKEN)
    station_filter = config.get(CONF_STATIONS)
    locations = config.get(CONF_LOCATIONS)

    client = waqiasync.WaqiClient(
        token, async_get_clientsession(hass), timeout=TIMEOUT)
    dev = []
    try:
        for location_name in locations:
            stations = await client.search(location_name)
            _LOGGER.debug("The following stations were returned: %s", stations)
            for station in stations:
                device = WaqiAirPollutant(client, station)
                if not station_filter or \
                    {device.uid,
                     device.url,
                     device.station_name} & set(station_filter):
                    dev.append(device)
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError):
        _LOGGER.exception('Failed to connect to WAQI servers.')
        raise PlatformNotReady
    async_add_entities(dev, True)


class WaqiAirPollutant(AirPollutantsEntity):
    """Implementation of a WAQI sensor."""

    def __init__(self, client, station):
        """Initialize the sensor."""
        self._client = client
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

        self._data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.station_name:
            return 'WAQI {}'.format(self.station_name)
        return 'WAQI {}'.format(self.url if self.url else self.uid)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:cloud'

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        try:
            return self._data.get('iaqi')['pm25']['v']
        except KeyError:
            return None

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        try:
            return self._data.get('iaqi')['pm10']['v']
        except KeyError:
            return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement of the temperature."""
        try:
            return self._data.get('iaqi')['t']['v']
        except KeyError:
            return None

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        try:
            return self._data.get('aqi')
        except KeyError:
            return None

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        try:
            return self._data.get('iaqi')['o3']['v']
        except KeyError:
            return None

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        try:
            return self._data.get('iaqi')['so2']['v']
        except KeyError:
            return None

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        try:
            return self._data.get('iaqi')['no2']['v']
        except KeyError:
            return None

    async def async_update(self):
        """Get the latest data and updates the states."""
        if self.uid:
            result = await self._client.get_station_by_number(self.uid)
        elif self.url:
            result = await self._client.get_station_by_name(self.url)
        else:
            result = None
        self._data = result
