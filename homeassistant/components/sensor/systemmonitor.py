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
    - type: 'swap_use_percent'
    - type: 'swap_use'
    - type: 'swap_free'
    - type: 'network_in'
      arg: 'eth0'
    - type: 'network_out'
      arg: 'eth0'
    - type: 'packets_in'
      arg: 'eth0'
    - type: 'packets_out'
      arg: 'eth0'
    - type: 'ipv4_address'
      arg: 'eth0'
    - type: 'ipv6_address'
      arg: 'eth0'
    - type: 'processor_use'
    - type: 'process'
      arg: 'octave-cli'
    - type: 'last_boot'
    - type: 'since_last_boot'

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
import logging
import psutil

import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_ON, STATE_OFF

REQUIREMENTS = ['psutil==3.0.0']
SENSOR_TYPES = {
    'disk_use_percent': ['Disk Use', '%'],
    'disk_use': ['Disk Use', 'GiB'],
    'disk_free': ['Disk Free', 'GiB'],
    'memory_use_percent': ['RAM Use', '%'],
    'memory_use': ['RAM Use', 'MiB'],
    'memory_free': ['RAM Free', 'MiB'],
    'processor_use': ['CPU Use', '%'],
    'process': ['Process', ''],
    'swap_use_percent': ['Swap Use', '%'],
    'swap_use': ['Swap Use', 'GiB'],
    'swap_free': ['Swap Free', 'GiB'],
    'network_out': ['Sent', 'MiB'],
    'network_in': ['Recieved', 'MiB'],
    'packets_out': ['Packets sent', ''],
    'packets_in': ['Packets recieved', ''],
    'ipv4_address': ['IPv4 address', ''],
    'ipv6_address': ['IPv6 address', ''],
    'last_boot': ['Last Boot', ''],
    'since_last_boot': ['Since Last Boot', '']
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

    # pylint: disable=too-many-branches
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
        elif self.type == 'swap_use_percent':
            self._state = psutil.swap_memory().percent
        elif self.type == 'swap_use':
            self._state = round(psutil.swap_memory().used / 1024**3, 1)
        elif self.type == 'swap_free':
            self._state = round(psutil.swap_memory().free / 1024**3, 1)
        elif self.type == 'processor_use':
            self._state = round(psutil.cpu_percent(interval=None))
        elif self.type == 'process':
            if any(self.argument in l.name() for l in psutil.process_iter()):
                self._state = STATE_ON
            else:
                self._state = STATE_OFF
        elif self.type == 'network_out':
            self._state = round(psutil.net_io_counters(pernic=True)
                                [self.argument][0] / 1024**2, 1)
        elif self.type == 'network_in':
            self._state = round(psutil.net_io_counters(pernic=True)
                                [self.argument][1] / 1024**2, 1)
        elif self.type == 'packets_out':
            self._state = psutil.net_io_counters(pernic=True)[self.argument][2]
        elif self.type == 'packets_in':
            self._state = psutil.net_io_counters(pernic=True)[self.argument][3]
        elif self.type == 'ipv4_address':
            self._state = psutil.net_if_addrs()[self.argument][0][1]
        elif self.type == 'ipv6_address':
            self._state = psutil.net_if_addrs()[self.argument][1][1]
        elif self.type == 'last_boot':
            self._state = dt_util.datetime_to_date_str(
                dt_util.as_local(
                    dt_util.utc_from_timestamp(psutil.boot_time())))
        elif self.type == 'since_last_boot':
            self._state = dt_util.utcnow() - dt_util.utc_from_timestamp(
                psutil.boot_time())
