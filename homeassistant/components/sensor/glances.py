"""
Support gathering system information of hosts which are running glances.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.glances/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_PORT, STATE_UNKNOWN, CONF_NAME, CONF_RESOURCES,
    TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'api/2/all'

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'Glances'
DEFAULT_PORT = '61208'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

SENSOR_TYPES = {
    'disk_use_percent': ['Disk used', '%'],
    'disk_use': ['Disk used', 'GiB'],
    'disk_free': ['Disk free', 'GiB'],
    'memory_use_percent': ['RAM used', '%'],
    'memory_use': ['RAM used', 'MiB'],
    'memory_free': ['RAM free', 'MiB'],
    'swap_use_percent': ['Swap used', '%'],
    'swap_use': ['Swap used', 'GiB'],
    'swap_free': ['Swap free', 'GiB'],
    'processor_load': ['CPU load', '15 min'],
    'process_running': ['Running', 'Count'],
    'process_total': ['Total', 'Count'],
    'process_thread': ['Thread', 'Count'],
    'process_sleeping': ['Sleeping', 'Count'],
    'cpu_temp': ['CPU Temp', TEMP_CELSIUS],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_RESOURCES, default=['disk_use']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Glances sensor."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    url = 'http://{}:{}/{}'.format(host, port, _RESOURCE)
    var_conf = config.get(CONF_RESOURCES)

    rest = GlancesData(url)
    rest.update()

    dev = []
    for resource in var_conf:
        dev.append(GlancesSensor(rest, name, resource))

    add_devices(dev, True)


class GlancesSensor(Entity):
    """Implementation of a Glances sensor."""

    def __init__(self, rest, name, sensor_type):
        """Initialize the sensor."""
        self.rest = rest
        self._name = name
        self.type = sensor_type
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._name is None:
            return SENSOR_TYPES[self.type][0]
        return '{} {}'.format(self._name, SENSOR_TYPES[self.type][0])

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.rest.data is not None

    @property
    def state(self):
        """Return the state of the resources."""
        return self._state

    def update(self):
        """Get the latest data from REST API."""
        self.rest.update()
        value = self.rest.data

        if value is not None:
            if self.type == 'disk_use_percent':
                self._state = value['fs'][0]['percent']
            elif self.type == 'disk_use':
                self._state = round(value['fs'][0]['used'] / 1024**3, 1)
            elif self.type == 'disk_free':
                try:
                    self._state = round(value['fs'][0]['free'] / 1024**3, 1)
                except KeyError:
                    self._state = round((value['fs'][0]['size'] -
                                         value['fs'][0]['used']) / 1024**3, 1)
            elif self.type == 'memory_use_percent':
                self._state = value['mem']['percent']
            elif self.type == 'memory_use':
                self._state = round(value['mem']['used'] / 1024**2, 1)
            elif self.type == 'memory_free':
                self._state = round(value['mem']['free'] / 1024**2, 1)
            elif self.type == 'swap_use_percent':
                self._state = value['memswap']['percent']
            elif self.type == 'swap_use':
                self._state = round(value['memswap']['used'] / 1024**3, 1)
            elif self.type == 'swap_free':
                self._state = round(value['memswap']['free'] / 1024**3, 1)
            elif self.type == 'processor_load':
                # Windows systems don't provide load details
                try:
                    self._state = value['load']['min15']
                except KeyError:
                    self._state = value['cpu']['total']
            elif self.type == 'process_running':
                self._state = value['processcount']['running']
            elif self.type == 'process_total':
                self._state = value['processcount']['total']
            elif self.type == 'process_thread':
                self._state = value['processcount']['thread']
            elif self.type == 'process_sleeping':
                self._state = value['processcount']['sleeping']
            elif self.type == 'cpu_temp':
                for sensor in value['sensors']:
                    if sensor['label'] == 'CPU':
                        self._state = sensor['value']
                self._state = None


class GlancesData(object):
    """The class for handling the data retrieval."""

    def __init__(self, resource):
        """Initialize the data object."""
        self._resource = resource
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Glances REST API."""
        try:
            response = requests.get(self._resource, timeout=10)
            self.data = response.json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Connection error: %s", self._resource)
            self.data = None
