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
    PLATFORM_SCHEMA, AirQualityEntity, PROP_TO_ATTR)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (ATTR_TIME, ATTR_TEMPERATURE, CONF_TOKEN)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['waqiasync==1.0.0']

_LOGGER = logging.getLogger(__name__)

ATTR_DOMINENTPOL = 'dominentpol'
ATTR_HUMIDITY = 'humidity'
ATTR_PRESSURE = 'pressure'

PROP_TO_ATTR.update({'temperature': ATTR_TEMPERATURE,
                     'humidity': ATTR_HUMIDITY,
                     'dominent_polluant': ATTR_DOMINENTPOL,
                     'update_time': ATTR_TIME,
                     'pressure': ATTR_PRESSURE})

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
    def attribution(self):
        """Return the attribution."""
        return [ATTRIBUTION] + [
            v['name'] for v in self._data.get('attributions', [])]

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self.extract_data('pm25')

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self.extract_data('pm10')

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return self._data.get('aqi')

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self.extract_data('o3')

    @property
    def humidity(self):
        """Return the humidity level."""
        return self.extract_data('h')

    @property
    def pressure(self):
        """Return the atmospheric pressure."""
        return self.extract_data('p')

    @property
    def temperature(self):
        """Return the temperature."""
        return self.extract_data('t')

    @property
    def carbon_monoxide(self):
        """Return the CO (carbon monoxide) level."""
        return self.extract_data('co')

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        return self.extract_data('so2')

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return self.extract_data('no2')

    @property
    def dominent_polluant(self):
        """Return the dominant polluant."""
        return self._data.get('dominentpol')

    @property
    def update_time(self):
        """Return the update time."""
        return self._data['time']['s']

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
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'µg/m3'

    def extract_data(self, key):
        """Extract the measurement value from API data."""
        if key in self._data['iaqi']:
            return self._data['iaqi'][key]['v']
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

    async def async_update(self):
        """Get the latest data and updates the states."""
        if self.uid:
            result = await self._client.get_station_by_number(self.uid)
        elif self.url:
            result = await self._client.get_station_by_name(self.url)
        else:
            result = None
        self._data = result
