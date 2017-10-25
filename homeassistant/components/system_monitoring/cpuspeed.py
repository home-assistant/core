"""
Support for displaying the current CPU speed.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/system_monitoring.cpuspeed/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.system_monitoring import (
    SystemMonitoring, PLATFORM_SCHEMA, CONF_SYSTEM)

REQUIREMENTS = ['py-cpuinfo==3.3.0']

_LOGGER = logging.getLogger(__name__)

ATTR_BRAND = 'Brand'
ATTR_HZ = 'GHz Advertised'
ATTR_ARCH = 'arch'

RESOURCE = 'cpu_speed'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SYSTEM): cv.string,
})


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the CPU speed resource."""
    system = config.get(CONF_SYSTEM)
    resource = RESOURCE

    add_devices([CpuSpeed(system, resource)], True)


class CpuSpeed(SystemMonitoring):
    """Representation of a CPU resource."""

    def __init__(self, system, resource):
        """Initialize the CPU resource."""
        self._system = system
        self._resource = resource
        self._state = None
        self.info = None

    @property
    def system(self):
        """Return the name of the monitored system."""
        return self._system

    @property
    def resource(self):
        """Return the name of the resource."""
        return self._resource

    @property
    def value(self):
        """Return the current value of the resource."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.info is not None:
            return {
                ATTR_ARCH: self.info['arch'],
                ATTR_BRAND: self.info['brand'],
                ATTR_HZ: round(self.info['hz_advertised_raw'][0]/10**9, 2)
            }

    def update(self):
        """Get the latest data and updates the state."""
        from cpuinfo import cpuinfo

        self.info = cpuinfo.get_cpu_info()
        self._state = round(float(self.info['hz_actual_raw'][0])/10**9, 2)
