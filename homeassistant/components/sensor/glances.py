"""
Support gahtering system information of hosts which are running glances.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.glances/
"""
import logging
from datetime import timedelta

import requests

from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

_RESOURCE = '/api/2/all'
CONF_HOST = 'host'
CONF_PORT = '61208'
CONF_RESOURCES = 'resources'
SENSOR_TYPES = {
    'disk_use_percent': ['Disk Use', '%'],
    'disk_use': ['Disk Use', 'GiB'],
    'disk_free': ['Disk Free', 'GiB'],
    'memory_use_percent': ['RAM Use', '%'],
    'memory_use': ['RAM Use', 'MiB'],
    'memory_free': ['RAM Free', 'MiB'],
    'swap_use_percent': ['Swap Use', '%'],
    'swap_use': ['Swap Use', 'GiB'],
    'swap_free': ['Swap Free', 'GiB'],
    'processor_load': ['CPU Load', None],
    'process_running': ['Running', None],
    'process_total': ['Total', None],
    'process_thread': ['Thread', None],
    'process_sleeping': ['Sleeping', None]
}

_LOGGER = logging.getLogger(__name__)
# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Glances sensor."""
    host = config.get(CONF_HOST)
    port = config.get('port', CONF_PORT)
    url = 'http://{}:{}{}'.format(host, port, _RESOURCE)
    var_conf = config.get(CONF_RESOURCES)

    if None in (host, var_conf):
        _LOGGER.error('Not all required config keys present: %s',
                      ', '.join((CONF_HOST, CONF_RESOURCES)))
        return False

    try:
        response = requests.get(url, timeout=10)
        if not response.ok:
            _LOGGER.error('Response status is "%s"', response.status_code)
            return False
    except requests.exceptions.MissingSchema:
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Please check the details in the configuration file")
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to resource/endpoint: %s", url)
        return False

    rest = GlancesData(url)

    dev = []
    for resource in var_conf:
        if resource not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', resource)
        else:
            dev.append(GlancesSensor(rest, config.get('name'), resource))

    add_devices(dev)


class GlancesSensor(Entity):
    """Implementation of a Glances sensor."""

    def __init__(self, rest, name, sensor_type):
        """Initialize the sensor."""
        self.rest = rest
        self._name = name
        self.type = sensor_type
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        """The name of the sensor."""
        if self._name is None:
            return SENSOR_TYPES[self.type][0]
        else:
            return '{} {}'.format(self._name, SENSOR_TYPES[self.type][0])

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    # pylint: disable=too-many-branches, too-many-return-statements
    @property
    def state(self):
        """Return the state of the resources."""
        value = self.rest.data

        if value is not None:
            if self.type == 'disk_use_percent':
                return value['fs'][0]['percent']
            elif self.type == 'disk_use':
                return round(value['fs'][0]['used'] / 1024**3, 1)
            elif self.type == 'disk_free':
                try:
                    return round(value['fs'][0]['free'] / 1024**3, 1)
                except KeyError:
                    return round((value['fs'][0]['size'] -
                                  value['fs'][0]['used']) / 1024**3, 1)
            elif self.type == 'memory_use_percent':
                return value['mem']['percent']
            elif self.type == 'memory_use':
                return round(value['mem']['used'] / 1024**2, 1)
            elif self.type == 'memory_free':
                return round(value['mem']['free'] / 1024**2, 1)
            elif self.type == 'swap_use_percent':
                return value['memswap']['percent']
            elif self.type == 'swap_use':
                return round(value['memswap']['used'] / 1024**3, 1)
            elif self.type == 'swap_free':
                return round(value['memswap']['free'] / 1024**3, 1)
            elif self.type == 'processor_load':
                return value['load']['min15']
            elif self.type == 'process_running':
                return value['processcount']['running']
            elif self.type == 'process_total':
                return value['processcount']['total']
            elif self.type == 'process_thread':
                return value['processcount']['thread']
            elif self.type == 'process_sleeping':
                return value['processcount']['sleeping']

    def update(self):
        """Get the latest data from REST API."""
        self.rest.update()


# pylint: disable=too-few-public-methods
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
            _LOGGER.error("No route to host/endpoint: %s", self._resource)
            self.data = None
