"""
Support for the Foobot indoor air quality monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.foobot/
"""
import asyncio
import logging
from datetime import timedelta, datetime
from collections import OrderedDict

import aiohttp
import voluptuous as vol

from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_TIME, ATTR_TEMPERATURE, CONF_TOKEN, CONF_USERNAME, TEMP_CELSIUS)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['foobot_async==0.3.0']

_LOGGER = logging.getLogger(__name__)

ATTR_HUMIDITY = 'humidity'
ATTR_PM2_5 = 'PM2.5'
ATTR_CARBON_DIOXIDE = 'CO2'
ATTR_VOLATILE_ORGANIC_COMPOUNDS = 'VOC'
ATTR_FOOBOT_INDEX = 'index'

SENSOR_TYPES = OrderedDict([('time', [ATTR_TIME, 's']),
                            ('pm', [ATTR_PM2_5, 'µg/m3', 'mdi:cloud']),
                            ('tmp', [ATTR_TEMPERATURE, TEMP_CELSIUS,
                                     'mdi:thermometer']),
                            ('hum', [ATTR_HUMIDITY, '%', 'mdi:water-percent']),
                            ('co2', [ATTR_CARBON_DIOXIDE, 'ppm',
                                     'mdi:periodic-table-co2']),
                            ('voc', [ATTR_VOLATILE_ORGANIC_COMPOUNDS, 'ppb',
                                     'mdi:cloud']),
                            ('allpollu', [ATTR_FOOBOT_INDEX, '%',
                                          'mdi:percent'])])

SCAN_INTERVAL = timedelta(minutes=10)
PARALLEL_UPDATES = 1

TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the devices associated with the account."""
    from foobot_async import FoobotClient

    token = config.get(CONF_TOKEN)
    username = config.get(CONF_USERNAME)

    client = FoobotClient(token, username,
                          async_get_clientsession(hass),
                          timeout=TIMEOUT)
    data = {}
    dev = []
    try:
        devices = yield from client.get_devices()
        _LOGGER.debug("The following devices were found: %s", devices)
        for device in devices:
            for sensor_type in SENSOR_TYPES.keys():
                if sensor_type != 'time':
                    foobot_sensor = FoobotSensor(client, data, device,
                                                 sensor_type)
                    dev.append(foobot_sensor)
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError, client.ClientError):
        _LOGGER.exception('Failed to connect to foobot servers.')
        raise PlatformNotReady
    async_add_devices(dev, True)


class FoobotSensor(Entity):
    """Implementation of a Foobot sensor."""

    def __init__(self, client, data, device, sensor_type):
        """Initialize the sensor."""
        self._client = client
        self._uuid = device['uuid']
        self._name = 'Foobot {} {}'.format(device['name'],
                                           SENSOR_TYPES[sensor_type][0])
        self.type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._last_request = datetime.utcfromtimestamp(0)
        self._data = data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return the state of the device."""
        try:
            data = self._data[self._uuid][self.type]
        except(KeyError, TypeError):
            data = None
        return data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data."""
        if self._uuid in self._data:
            _LOGGER.debug('last_update: %s', self._last_request)
            _LOGGER.debug('now: %s', datetime.utcnow())
            if self._last_request + SCAN_INTERVAL > datetime.utcnow():
                # If the last request made is recent enough,
                # just skip the update
                return

        interval = SCAN_INTERVAL.total_seconds()
        try:
            response = yield from self._client.get_last_data(self._uuid,
                                                             interval,
                                                             interval + 1)
        except (aiohttp.client_exceptions.ClientConnectorError,
                asyncio.TimeoutError, self._client.ClientError):
            _LOGGER.exception('Failed to fetch data from foobot servers.')
            raise PlatformNotReady
        if response:
            _LOGGER.debug("The data response is: %s", response)
            self._last_request = datetime.utcnow()
            self._data[self._uuid] = {k: round(v, 1) for k, v in
                                      response[0].items()}
