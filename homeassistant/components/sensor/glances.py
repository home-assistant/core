"""
homeassistant.components.sensor.glances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gathers system information of hosts which running glances.

Configuration:

To use the glances sensor you will need to add something like the following
to your configuration.yaml file.

sensor:
  platform: glances
  name: Glances sensor
  host: IP_ADDRESS
  port: 61208
  resources:
    - 'disk_use_percent'
    - 'disk_use'
    - 'disk_free'
    - 'memory_use_percent'
    - 'memory_use'
    - 'memory_free'
    - 'swap_use_percent'
    - 'swap_use'
    - 'swap_free'
    - 'processor_load'
    - 'process_running'
    - 'process_total'
    - 'process_thread'
    - 'process_sleeping'

Variables:

name
*Optional
The name of the sensor. Default is 'Glances Sensor'.

host
*Required
The IP address of your host, e.g. 192.168.1.32.

port
*Optional
The network port to connect to. Default is 61208.

resources
*Required
Resources to monitor on the host. See the configuration example above for a
list of all available conditions to monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.glances.html
"""
import logging
import requests
from datetime import timedelta

from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Glances Sensor'
_RESOURCE = '/api/2/all'
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
    'processor_load': ['CPU Load', ''],
    'process_running': ['Running', ''],
    'process_total': ['Total', ''],
    'process_thread': ['Thread', ''],
    'process_sleeping': ['Sleeping', '']
}

_LOGGER = logging.getLogger(__name__)
# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup the Glances sensor. """

    if not config.get('host'):
        _LOGGER.error('"host:" is missing your configuration')
        return False

    host = config.get('host')
    port = config.get('port', 61208)
    url = 'http://{}:{}{}'.format(host, port, _RESOURCE)

    try:
        response = requests.get(url, timeout=10)
        if not response.ok:
            _LOGGER.error('Response status is "%s"', response.status_code)
            return False
    except requests.exceptions.MissingSchema:
        _LOGGER.error('Missing resource or schema in configuration. '
                      'Please heck our details in the configuration file.')
        return False
    except requests.exceptions.ConnectionError:
        _LOGGER.error('No route to resource/endpoint. '
                      'Please check the details in the configuration file.')
        return False

    rest = GlancesData(url)

    dev = []
    for resource in config['resources']:
        if resource not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', resource)
        else:
            dev.append(GlancesSensor(rest, resource))

    add_devices(dev)


class GlancesSensor(Entity):
    """ Implements a REST sensor. """

    def __init__(self, rest, sensor_type):
        self.rest = rest
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        """ The name of the sensor. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return self._unit_of_measurement

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    # pylint: disable=too-many-branches
    def update(self):
        """ Gets the latest data from REST API and updates the state. """
        self.rest.update()
        value = self.rest.data

        if value is not None:
            if self.type == 'disk_use_percent':
                self._state = value['fs'][0]['percent']
            elif self.type == 'disk_use':
                self._state = round(value['fs'][0]['used'] / 1024**3, 1)
            elif self.type == 'disk_free':
                self._state = round(value['fs'][0]['free'] / 1024**3, 1)
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
                self._state = value['load']['min15']
            elif self.type == 'process_running':
                self._state = value['processcount']['running']
            elif self.type == 'process_total':
                self._state = value['processcount']['total']
            elif self.type == 'process_thread':
                self._state = value['processcount']['thread']
            elif self.type == 'process_sleeping':
                self._state = value['processcount']['sleeping']


# pylint: disable=too-few-public-methods
class GlancesData(object):
    """ Class for handling the data retrieval. """

    def __init__(self, resource):
        self.resource = resource
        self.data = dict()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from REST service. """
        try:
            response = requests.get(self.resource, timeout=10)
            self.data = response.json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to host/endpoint.")
            self.data = None
