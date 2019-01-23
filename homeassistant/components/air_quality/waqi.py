"""
Support for the World Air Quality Index service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/air_quality.waqi/
"""
import asyncio
import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol

from homeassistant.components.air_quality import (
    PLATFORM_SCHEMA, AirQualityEntity, ATTR_ATTRIBUTION, ATTR_NO2,
    ATTR_OZONE, ATTR_PM_10, ATTR_PM_2_5, ATTR_SO2)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (ATTR_TIME, ATTR_TEMPERATURE, CONF_TOKEN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['waqiasync==1.0.0']

_LOGGER = logging.getLogger(__name__)

ATTR_DOMINENTPOL = 'dominentpol'
ATTR_HUMIDITY = 'humidity'
ATTR_PRESSURE = 'pressure'

KEY_TO_ATTR = {
    'pm25': ATTR_PM_2_5,
    'pm10': ATTR_PM_10,
    'h': ATTR_HUMIDITY,
    'p': ATTR_PRESSURE,
    't': ATTR_TEMPERATURE,
    'o3': ATTR_OZONE,
    'no2': ATTR_NO2,
    'so2': ATTR_SO2,
}

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
                waqi_entity = WaqiQuality(client, station)
                if not station_filter or \
                    {waqi_entity.uid,
                     waqi_entity.url,
                     waqi_entity.station_name} & set(station_filter):
                    dev.append(waqi_entity)
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError):
        _LOGGER.exception('Failed to connect to WAQI servers.')
        raise PlatformNotReady
    async_add_entities(dev, True)


class WaqiQuality(AirQualityEntity):
    """Implementation of a WAQI air quality entity."""

    def __init__(self, client, station):
        """Initialize the entity."""
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
        """Return the name of the entity."""
        if self.station_name:
            return 'WAQI {}'.format(self.station_name)
        return 'WAQI {}'.format(self.url if self.url else self.uid)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:cloud'

    @property
    def state(self):
        """Return the state of the device."""
        if self._data is not None:
            return self._data.get('aqi')
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'AQI'

    @property
    def state_attributes(self):
        """Return the state attributes of the last update."""
        attrs = {}

        if self._data is not None:
            try:
                attrs[ATTR_ATTRIBUTION] = ' and '.join(
                    [ATTRIBUTION] + [
                        v['name'] for v in self._data.get('attributions', [])])

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
                return {ATTR_ATTRIBUTION: ATTRIBUTION}

    async def async_update(self):
        """Get the latest data and updates the states."""
        if self.uid:
            result = await self._client.get_station_by_number(self.uid)
        elif self.url:
            result = await self._client.get_station_by_name(self.url)
        else:
            result = None
        self._data = result
