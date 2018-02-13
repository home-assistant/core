"""
Support for monitoring the local system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.systemmonitor/
"""
import logging
import os

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_RESOURCES, STATE_OFF, STATE_ON, STATE_UNKNOWN, CONF_TYPE)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['psutil==5.4.3']

_LOGGER = logging.getLogger(__name__)

CONF_ARG = 'arg'

SENSOR_TYPES = {
    'disk_free': ['Disk free', 'GiB', 'mdi:harddisk'],
    'disk_use': ['Disk use', 'GiB', 'mdi:harddisk'],
    'disk_use_percent': ['Disk use (percent)', '%', 'mdi:harddisk'],
    'ipv4_address': ['IPv4 address', '', 'mdi:server-network'],
    'ipv6_address': ['IPv6 address', '', 'mdi:server-network'],
    'last_boot': ['Last boot', '', 'mdi:clock'],
    'load_15m': ['Load (15m)', '', 'mdi:memory'],
    'load_1m': ['Load (1m)', '', 'mdi:memory'],
    'load_5m': ['Load (5m)', '', 'mdi:memory'],
    'memory_free': ['Memory free', 'MiB', 'mdi:memory'],
    'memory_use': ['Memory use', 'MiB', 'mdi:memory'],
    'memory_use_percent': ['Memory use (percent)', '%', 'mdi:memory'],
    'network_in': ['Network in', 'MiB', 'mdi:server-network'],
    'network_out': ['Network out', 'MiB', 'mdi:server-network'],
    'packets_in': ['Packets in', ' ', 'mdi:server-network'],
    'packets_out': ['Packets out', ' ', 'mdi:server-network'],
    'process': ['Process', ' ', 'mdi:memory'],
    'processor_use': ['Processor use', '%', 'mdi:memory'],
    'since_last_boot': ['Since last boot', '', 'mdi:clock'],
    'swap_free': ['Swap free', 'GiB', 'mdi:harddisk'],
    'swap_use': ['Swap use', 'GiB', 'mdi:harddisk'],
    'swap_use_percent': ['Swap use (percent)', '%', 'mdi:harddisk'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_RESOURCES, default=['disk_use']):
        vol.All(cv.ensure_list, [vol.Schema({
            vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
            vol.Optional(CONF_ARG): cv.string,
        })])
})

IO_COUNTER = {
    'network_out': 0,
    'network_in': 1,
    'packets_out': 2,
    'packets_in': 3,
}

IF_ADDRS = {
    'ipv4_address': 0,
    'ipv6_address': 1,
}


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the system monitor sensors."""
    dev = []
    for resource in config[CONF_RESOURCES]:
        if CONF_ARG not in resource:
            resource[CONF_ARG] = ''
        dev.append(SystemMonitorSensor(
            resource[CONF_TYPE], resource[CONF_ARG]))

    add_devices(dev, True)


class SystemMonitorSensor(Entity):
    """Implementation of a system monitor sensor."""

    def __init__(self, sensor_type, argument=''):
        """Initialize the sensor."""
        self._name = '{} {}'.format(SENSOR_TYPES[sensor_type][0], argument)
        self.argument = argument
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

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
            virtual_memory = psutil.virtual_memory()
            self._state = round((virtual_memory.total -
                                 virtual_memory.available) /
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
            for proc in psutil.process_iter():
                try:
                    if self.argument == proc.name():
                        self._state = STATE_ON
                        return
                except psutil.NoSuchProcess as err:
                    _LOGGER.warning(
                        "Failed to load process with id: %s, old name: %s",
                        err.pid, err.name)
            self._state = STATE_OFF
        elif self.type == 'network_out' or self.type == 'network_in':
            counters = psutil.net_io_counters(pernic=True)
            if self.argument in counters:
                counter = counters[self.argument][IO_COUNTER[self.type]]
                self._state = round(counter / 1024**2, 1)
            else:
                self._state = STATE_UNKNOWN
        elif self.type == 'packets_out' or self.type == 'packets_in':
            counters = psutil.net_io_counters(pernic=True)
            if self.argument in counters:
                self._state = counters[self.argument][IO_COUNTER[self.type]]
            else:
                self._state = STATE_UNKNOWN
        elif self.type == 'ipv4_address' or self.type == 'ipv6_address':
            addresses = psutil.net_if_addrs()
            if self.argument in addresses:
                self._state = addresses[self.argument][IF_ADDRS[self.type]][1]
            else:
                self._state = STATE_UNKNOWN
        elif self.type == 'last_boot':
            self._state = dt_util.as_local(
                dt_util.utc_from_timestamp(psutil.boot_time())
            ).date().isoformat()
        elif self.type == 'since_last_boot':
            self._state = dt_util.utcnow() - dt_util.utc_from_timestamp(
                psutil.boot_time())
        elif self.type == 'load_1m':
            self._state = os.getloadavg()[0]
        elif self.type == 'load_5m':
            self._state = os.getloadavg()[1]
        elif self.type == 'load_15m':
            self._state = os.getloadavg()[2]
