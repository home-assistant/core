"""
Support for the Foobot indoor air quality monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/air_quality.foobot/
"""
import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp
import voluptuous as vol

from homeassistant.components.air_quality import (
    AirQualityEntity, ATTR_AQI, ATTR_PM_2_5, ATTR_CO2, ATTR_ATTRIBUTION,
    PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.const import (
    ATTR_TIME, ATTR_TEMPERATURE, CONF_TOKEN, CONF_USERNAME)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_FOOBOT_INDEX = 'foobot_index'
ATTR_HUMIDITY = 'humidity'
ATTR_VOC = 'volatile_organic_compound'

PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})

PROP_TO_ATTR = {
    'air_quality_index': ATTR_AQI,
    'attribution': ATTR_ATTRIBUTION,
    'carbon_dioxide': ATTR_CO2,
    'foobot_index': ATTR_FOOBOT_INDEX,
    'humidity': ATTR_HUMIDITY,
    'particulate_matter_2_5': ATTR_PM_2_5,
    'temperature': ATTR_TEMPERATURE,
    'update_time': ATTR_TIME,
    'volatile_organic_compound': ATTR_VOC,
}

REQUIREMENTS = ['foobot_async==0.3.1']

SCAN_INTERVAL = timedelta(minutes=10)

TIMEOUT = 10


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the devices associated with the account."""
    from foobot_async import FoobotClient

    token = config.get(CONF_TOKEN)
    username = config.get(CONF_USERNAME)

    client = FoobotClient(token, username,
                          async_get_clientsession(hass),
                          timeout=TIMEOUT)
    dev = []
    try:
        devices = await client.get_devices()
        _LOGGER.debug("The following devices were found: %s", devices)
        for device in devices:
            foobot_data = FoobotData(client, device['uuid'])
            foobot_device = FoobotQuality(foobot_data, device)
            dev.append(foobot_device)
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError, FoobotClient.TooManyRequests,
            FoobotClient.InternalError):
        _LOGGER.exception('Failed to connect to foobot servers.')
        raise PlatformNotReady
    except FoobotClient.ClientError:
        _LOGGER.error('Failed to fetch data from foobot servers.')
        return
    async_add_entities(dev, True)


class FoobotQuality(AirQualityEntity):
    """Implementation of a Foobot Air Quality Monitor."""

    def __init__(self, data, device):
        """Initialize the air quality entity."""
        self._uuid = device['uuid']
        self._attribution = 'Foobot®—Airboxlab S.A.S.'
        self._icon = 'mdi:cloud'
        self._name = 'Foobot {}'.format(device['name'])
        self._unit_of_measurement = 'µg/m3'
        self.foobot_data = data

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return self.pm_2_5_to_aqi(self.particulate_matter_2_5)

    @property
    def attribution(self):
        """Return the attribution."""
        return self._attribution

    @property
    def carbon_dioxide(self):
        """Return the CO2 (carbon dioxide) level."""
        return self.foobot_data.data['co2']

    @property
    def foobot_index(self):
        """Return the foobot index."""
        return self.foobot_data.data['allpollu']

    @property
    def humidity(self):
        """Return the humidity."""
        return self.foobot_data.data['hum']

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self.foobot_data.data['pm']

    @property
    def temperature(self):
        """Return the temperature."""
        return self.foobot_data.data['tmp']

    @property
    def update_time(self):
        """Return the time of the measurements."""
        return datetime.utcfromtimestamp(
            self.foobot_data.data['time']).strftime('%Y-%m-%dT%H:%M:%SZ')

    @property
    def unique_id(self):
        """Return the unique id of this entity."""
        return self._uuid

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def volatile_organic_compound(self):
        """Return the VOC (volatile organic compound) level."""
        return self.foobot_data.data['voc']

    async def async_update(self):
        """Get the latest data."""
        await self.foobot_data.async_update()

    @staticmethod
    def pm_2_5_to_aqi(pm_level):
        """Convert PM 2.5 level in µg/m3 to AQI using the US EPA formula."""
        # A table is needed because it's not linear, some ranges have different
        # coefficents [pm_min, pm_max, aqi_min, aqi_max]
        ranges = [[0, 12, 0, 50],
                  [12.1, 35.4, 51, 100],
                  [35.5, 55.4, 101, 150],
                  [55.5, 150.4, 151, 200],
                  [150.5, 250.4, 201, 300],
                  [250.5, 350.4, 301, 400],
                  [350.5, 500.4, 401, 500]]
        if pm_level > 500.4:
            return 500

        for levels in ranges:
            if levels[0] <= pm_level <= levels[1]:
                return int(levels[2]
                           + ((levels[3] - levels[2])
                              / (levels[1] - levels[0]))
                           * (pm_level - levels[0]))

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data


class FoobotData:
    """Get data from Foobot API."""

    def __init__(self, client, uuid):
        """Initialize the data object."""
        self._client = client
        self._uuid = uuid
        self.data = {}

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the data from Foobot API."""
        interval = SCAN_INTERVAL.total_seconds()
        try:
            response = await self._client.get_last_data(self._uuid,
                                                        interval,
                                                        interval + 1)
        except (aiohttp.client_exceptions.ClientConnectorError,
                asyncio.TimeoutError, self._client.TooManyRequests,
                self._client.InternalError):
            _LOGGER.debug("Couldn't fetch data")
            return False
        _LOGGER.debug("The data response is: %s", response)
        self.data = {k: round(v, 1) for k, v in response[0].items()}
        return True
