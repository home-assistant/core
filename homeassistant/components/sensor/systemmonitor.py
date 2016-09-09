"""
Support for monitoring the local system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.systemmonitor/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_RESOURCES, STATE_OFF, STATE_ON)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['psutil==4.3.1']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'disk_use_percent': ['Disk Use', '%', 'mdi:harddisk'],
    'disk_use': ['Disk Use', 'GiB', 'mdi:harddisk'],
    'disk_free': ['Disk Free', 'GiB', 'mdi:harddisk'],
    'memory_use_percent': ['RAM Use', '%', 'mdi:memory'],
    'memory_use': ['RAM Use', 'MiB', 'mdi:memory'],
    'memory_free': ['RAM Free', 'MiB', 'mdi:memory'],
    'processor_use': ['CPU Use', '%', 'mdi:memory'],
    'process': ['Process', '', 'mdi:memory'],
    'swap_use_percent': ['Swap Use', '%', 'mdi:harddisk'],
    'swap_use': ['Swap Use', 'GiB', 'mdi:harddisk'],
    'swap_free': ['Swap Free', 'GiB', 'mdi:harddisk'],
    'network_out': ['Sent', 'MiB', 'mdi:server-network'],
    'network_in': ['Received', 'MiB', 'mdi:server-network'],
    'packets_out': ['Packets sent', '', 'mdi:server-network'],
    'packets_in': ['Packets received', '', 'mdi:server-network'],
    'ipv4_address': ['IPv4 address', '', 'mdi:server-network'],
    'ipv6_address': ['IPv6 address', '', 'mdi:server-network'],
    'last_boot': ['Last Boot', '', 'mdi:clock'],
    'since_last_boot': ['Since Last Boot', '', 'mdi:clock']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_RESOURCES, default=['disk_use']):
        vol.All(cv.ensure_list, [vol.Schema({
            vol.Required('type'): vol.In(SENSOR_TYPES),
            vol.Optional('arg'): cv.string,
        })])
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the System sensors."""
    dev = []
    for resource in config[CONF_RESOURCES]:
        if 'arg' not in resource:
            resource['arg'] = ''
        dev.append(SystemMonitorSensor(resource['type'], resource['arg']))

    add_devices(dev)


class SystemMonitorSensor(Entity):
    """Implementation of a system monitor sensor."""

    def __init__(self, sensor_type, argument=''):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0] + ' ' + argument
        self.argument = argument
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name.rstrip()

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    # pylint: disable=too-many-branches
    def update(self):
        """Get the latest system information."""
        import psutil
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
            self._state = dt_util.as_local(
                dt_util.utc_from_timestamp(psutil.boot_time())
            ).date().isoformat()
        elif self.type == 'since_last_boot':
            self._state = dt_util.utcnow() - dt_util.utc_from_timestamp(
                psutil.boot_time())
