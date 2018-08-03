"""
Support for Start.ca Bandwidth Monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.startca/
"""
from datetime import timedelta
from xml.parsers.expat import ExpatError
import logging
import asyncio
import async_timeout

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_MONITORED_VARIABLES, CONF_NAME)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['xmltodict==0.11.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Start.ca'
CONF_TOTAL_BANDWIDTH = 'total_bandwidth'

GIGABYTES = 'GB'  # type: str
PERCENT = '%'  # type: str

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)
REQUEST_TIMEOUT = 5  # seconds

SENSOR_TYPES = {
    'usage': ['Usage Ratio', PERCENT, 'mdi:percent'],
    'usage_gb': ['Usage', GIGABYTES, 'mdi:download'],
    'limit': ['Data limit', GIGABYTES, 'mdi:download'],
    'used_download': ['Used Download', GIGABYTES, 'mdi:download'],
    'used_upload': ['Used Upload', GIGABYTES, 'mdi:upload'],
    'used_total': ['Used Total', GIGABYTES, 'mdi:download'],
    'grace_download': ['Grace Download', GIGABYTES, 'mdi:download'],
    'grace_upload': ['Grace Upload', GIGABYTES, 'mdi:upload'],
    'grace_total': ['Grace Total', GIGABYTES, 'mdi:download'],
    'total_download': ['Total Download', GIGABYTES, 'mdi:download'],
    'total_upload': ['Total Upload', GIGABYTES, 'mdi:download'],
    'used_remaining': ['Remaining', GIGABYTES, 'mdi:download']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_TOTAL_BANDWIDTH): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor platform."""
    websession = async_get_clientsession(hass)
    apikey = config.get(CONF_API_KEY)
    bandwidthcap = config.get(CONF_TOTAL_BANDWIDTH)

    ts_data = StartcaData(hass.loop, websession, apikey, bandwidthcap)
    ret = yield from ts_data.async_update()
    if ret is False:
        _LOGGER.error("Invalid Start.ca API key: %s", apikey)
        return

    name = config.get(CONF_NAME)
    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(StartcaSensor(ts_data, variable, name))
    async_add_devices(sensors, True)


class StartcaSensor(Entity):
    """Representation of Start.ca Bandwidth sensor."""

    def __init__(self, startcadata, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.startcadata = startcadata
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from Start.ca and update the state."""
        yield from self.startcadata.async_update()
        if self.type in self.startcadata.data:
            self._state = round(self.startcadata.data[self.type], 2)


class StartcaData:
    """Get data from Start.ca API."""

    def __init__(self, loop, websession, api_key, bandwidth_cap):
        """Initialize the data object."""
        self.loop = loop
        self.websession = websession
        self.api_key = api_key
        self.bandwidth_cap = bandwidth_cap
        # Set unlimited users to infinite, otherwise the cap.
        self.data = {"limit": self.bandwidth_cap} if self.bandwidth_cap > 0 \
            else {"limit": float('inf')}

    @staticmethod
    def bytes_to_gb(value):
        """Convert from bytes to GB.

        :param value: The value in bytes to convert to GB.
        :return: Converted GB value
        """
        return float(value) * 10 ** -9

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the Start.ca bandwidth data from the web service."""
        import xmltodict
        _LOGGER.debug("Updating Start.ca usage data")
        url = 'https://www.start.ca/support/usage/api?key=' + \
              self.api_key
        with async_timeout.timeout(REQUEST_TIMEOUT, loop=self.loop):
            req = await self.websession.get(url)
        if req.status != 200:
            _LOGGER.error("Request failed with status: %u", req.status)
            return False

        data = await req.text()
        try:
            xml_data = xmltodict.parse(data)
        except ExpatError:
            return False

        used_dl = self.bytes_to_gb(xml_data['usage']['used']['download'])
        used_ul = self.bytes_to_gb(xml_data['usage']['used']['upload'])
        grace_dl = self.bytes_to_gb(xml_data['usage']['grace']['download'])
        grace_ul = self.bytes_to_gb(xml_data['usage']['grace']['upload'])
        total_dl = self.bytes_to_gb(xml_data['usage']['total']['download'])
        total_ul = self.bytes_to_gb(xml_data['usage']['total']['upload'])

        limit = self.data['limit']
        if self.bandwidth_cap > 0:
            self.data['usage'] = 100*used_dl/self.bandwidth_cap
        else:
            self.data['usage'] = 0
        self.data['usage_gb'] = used_dl
        self.data['used_download'] = used_dl
        self.data['used_upload'] = used_ul
        self.data['used_total'] = used_dl + used_ul
        self.data['grace_download'] = grace_dl
        self.data['grace_upload'] = grace_ul
        self.data['grace_total'] = grace_dl + grace_ul
        self.data['total_download'] = total_dl
        self.data['total_upload'] = total_ul
        self.data['used_remaining'] = limit - used_dl

        return True
