"""
homeassistant.components.sensor.systemmonitor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shows system monitor values such as: disk, memory and processor use

Configuration:

To use the System monitor sensor you will need to add something like the
following to your config/configuration.yaml

sensor:
  platform: systemmonitor
  resources:
    - type: 'disk_use_percent'
      arg: '/'
    - type: 'disk_use'
      arg: '/home'
    - type: 'disk_free'
      arg: '/'
    - type: 'memory_use_percent'
    - type: 'memory_use'
    - type: 'memory_free'
    - type: 'processor_use'
    - type: 'process'
      arg: 'octave-cli'

Variables:

resources
*Required
An array specifying the variables to monitor.

These are the variables for the resources array:

type
*Required
The variable you wish to monitor, see the configuration example above for a
sample list of variables.

arg
*Optional
Additional details for the type, eg. path, binary name, etc.
"""

from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_ON, STATE_OFF
import psutil
import logging


SENSOR_TYPES = {
    'disk_use_percent': ['Disk Use', '%'],
    'disk_use': ['Disk Use', 'GiB'],
    'disk_free': ['Disk Free', 'GiB'],
    'memory_use_percent': ['RAM Use', '%'],
    'memory_use': ['RAM Use', 'MiB'],
    'memory_free': ['RAM Free', 'MiB'],
    'processor_use': ['CPU Use', '%'],
    'process': ['Process', ''],
}

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors. """

    dev = []
    for resource in config['resources']:
        if 'arg' not in resource:
            resource['arg'] = ''
        if resource['type'] not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', resource['type'])
        else:
            dev.append(SystemMonitorSensor(resource['type'], resource['arg']))

    add_devices(dev)


class SystemMonitorSensor(Entity):
    """ A system monitor sensor. """

    def __init__(self, sensor_type, argument=''):
        self._name = SENSOR_TYPES[sensor_type][0] + ' ' + argument
        self.argument = argument
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    def update(self):
        if self.type == 'disk_use_percent':
            self._state = psutil.disk_usage(self.argument).percent
        elif self.type == 'disk_use':
            self._state = round(psutil.disk_usage(self.argument).used /
                                1024**3, 1)
        elif self.type == 'disk_free':
            self._state = round(psutil.disk_usage(self.argument).free /
                                1024**3, 1)
        elif self.type == 'memory_use_percent':
            self._state = psutil.virtual_memory().percent
        elif self.type == 'memory_use':
            self._state = round((psutil.virtual_memory().total -
                                 psutil.virtual_memory().available) /
                                1024**2, 1)
        elif self.type == 'memory_free':
            self._state = round(psutil.virtual_memory().available / 1024**2, 1)
        elif self.type == 'processor_use':
            self._state = round(psutil.cpu_percent(interval=None))
        elif self.type == 'process':
            if any(self.argument in l.name() for l in psutil.process_iter()):
                self._state = STATE_ON
            else:
                self._state = STATE_OFF
