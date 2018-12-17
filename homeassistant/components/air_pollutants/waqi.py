"""
Component for handling Air Pollutants data for your location.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/air_pollutants.waqi/
"""
import asyncio
from datetime import timedelta
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.air_pollutants import AirPollutantsEntity
from homeassistant.const import ATTR_TEMPERATURE, CONF_TOKEN
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA

ATTR_DOMINENTPOL = 'dominentpol'
ATTR_HUMIDITY = 'humidity'
ATTR_PRESSURE = 'pressure'

KEY_TO_ATTR = {
    'h': ATTR_HUMIDITY,
    'p': ATTR_PRESSURE,
    't': ATTR_TEMPERATURE,
}

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

    token = config[CONF_TOKEN]
    station_filter = config.get(CONF_STATIONS)
    locations = config[CONF_LOCATIONS]

    client = waqiasync.WaqiClient(
        token, async_get_clientsession(hass), timeout=TIMEOUT)

    dev = []
    try:
        for location_name in locations:
            stations = await client.search(location_name)
            _LOGGER.debug("The following stations were returned: %s", stations)
            for station in stations:
                waqi_air_pollutant = WaqiAirPollutant(client, station)
                if not station_filter or \
                    {waqi_air_pollutant.uid,
                     waqi_air_pollutant.url,
                     waqi_air_pollutant.station_name} & set(station_filter):
                    dev.append(waqi_air_pollutant)
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError):
        _LOGGER.exception('Failed to connect to WAQI servers.')
        raise PlatformNotReady
    async_add_entities(dev, True)


class WaqiAirPollutant(AirPollutantsEntity):
    """Implementation of a WAQI Air Pollutant."""

    def __init__(self, client, station):
        self._client = client
        self.uid = station.get('uid', None)
        self.url = station.get('station', {}).get('url', None)
        self.station_name = station.get('station', {}).get('name', None)
        self._data = None
    
    @property
    def name(self):
        """Return the name of the sensor."""
        if self.station_name:
            return 'WAQI {}'.format(self.station_name)
        return 'WAQI {}'.format(self.url if self.url else self.uid)

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        try:
            return self._data['iaqi']['pm25']['v']
        except (IndexError, KeyError):
            return None

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        try:
            return self._data['iaqi']['pm10']['v']
        except (IndexError, KeyError):
            return None

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        if self._data is not None:
            return self._data.get('aqi')
        return None

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        try:
            return self._data['iaqi']['o3']['v']
        except (IndexError, KeyError):
            return None

    @property
    def attribution(self):
        """Return the attribution."""
        attribution = ATTRIBUTION
        if self._data is not None:
            try:
                attribution = ' and '.join([ATTRIBUTION] + [
                    v['name'] for v in self._data.get('attributions', [])])
            except (IndexError, KeyError):
                pass
        return attribution

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        try:
            return self._data['iaqi']['so2']['v']
        except (IndexError, KeyError):
            return None

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        try:
            return self._data['iaqi']['no2']['v']
        except (IndexError, KeyError):
            return None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the last update."""
        attrs = {}
        if self._data is not None:
            try:
                attrs[ATTR_TIME] = self._data['time']['s']
                attrs[ATTR_DOMINENTPOL] = self._data.get('dominentpol')

                iaqi = self._data['iaqi']
                for key in iaqi:
                    if key in KEY_TO_ATTR:
                        attrs[KEY_TO_ATTR[key]] = iaqi[key]['v']
                    else:
                        attrs[key] = iaqi[key]['v']

                return attrs
            except (IndexError, KeyError):
                pass

    async def async_update(self):
        """Get the latest data and updates the states."""
        if self.uid:
            result = await self._client.get_station_by_number(self.uid)
        elif self.url:
            result = await self._client.get_station_by_name(self.url)
        else:
            result = None
        self._data = result
