"""
homeassistant.components.sensor.systemmonitor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shows system monitor values such as: disk, memory and processor use

"""

from homeassistant.helpers.device import Device
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, ATTR_FRIENDLY_NAME)
import psutil
import logging

sensor_types = {
    'disk_use_percent': ['Disk Use', '%'],
    'disk_use': ['Disk Use', 'GiB'],
    'disk_free': ['Disk Free', 'GiB'],
    'memory_use_percent': ['RAM Use', '%'],
    'memory_use': ['RAM Use', 'MiB'],
    'memory_free': ['RAM Free', 'MiB'],
    'processor_use': ['CPU Use', '%'],
}

_LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors """

    devices = []
    for resurce in config['resources']:
        if 'arg' not in resurce:
            resurce['arg'] = ''
        if resurce['type'] not in sensor_types:
            _LOGGER.error('Sensor type: "%s" does not exist', resurce['type'])
        else:
            devices.append(SystemMonitorSensor(resurce['type'], resurce['arg']))

    add_devices(devices)


class SystemMonitorSensor(Device):
    """ A system monitor sensor """

    def __init__(self, type, argument=''):
        self._name = sensor_types[type][0] + ' ' + argument
        self.argument = argument
        self.type = type
        self._state = None
        self.unit_of_measurement = sensor_types[type][1]
        self.update()

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        return {
            ATTR_FRIENDLY_NAME: self.name,
            ATTR_UNIT_OF_MEASUREMENT: self.unit_of_measurement,
        }

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
