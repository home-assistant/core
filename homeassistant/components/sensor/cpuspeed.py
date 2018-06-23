"""
Support for displaying the current CPU speed.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.cpuspeed/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['py-cpuinfo==4.0.0']

_LOGGER = logging.getLogger(__name__)

ATTR_BRAND = 'Brand'
ATTR_HZ = 'GHz Advertised'
ATTR_ARCH = 'arch'

DEFAULT_NAME = 'CPU speed'

ICON = 'mdi:pulse'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the CPU speed sensor."""
    name = config.get(CONF_NAME)

    add_devices([CpuSpeedSensor(name)], True)


class CpuSpeedSensor(Entity):
    """Representation of a CPU sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self.info = None
        self._unit_of_measurement = 'GHz'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.info is not None:
            return {
                ATTR_ARCH: self.info['arch'],
                ATTR_BRAND: self.info['brand'],
                ATTR_HZ: round(self.info['hz_advertised_raw'][0]/10**9, 2)
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the state."""
        from cpuinfo import cpuinfo

        self.info = cpuinfo.get_cpu_info()
        self._state = round(float(self.info['hz_actual_raw'][0])/10**9, 2)
