"""
Platform for Roth Touchline heat pump controller.

Example configuration:
climate:
  - platform: touchline
    host: http://192.168.1.1

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.touchline/
"""

import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pytouchline==0.5']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Touchline devices."""
    from pytouchline import PyTouchline
    host = config[CONF_HOST]
    py_touchline = PyTouchline()
    number_of_devices = int(py_touchline.get_number_of_devices(host))
    devices = []
    for device_id in range(0, numberOfDevices):
        devices.append(Touchline(PyTouchline(device_id)))
    add_devices(devices)


class Touchline(ClimateDevice):
    """Representation of a Touchline device."""

    def __init__(self, touchline_thermostat):
        """Initialize the climate device."""
        self.unit = touchline_thermostat
        self.unit.update()
        self._name = self.unit.get_name()
        self._current_temperature = self.unit.get_current_temperature()

    def update(self):
        """Update unit attributes."""
        self.unit.update()
        self._name = self.unit.get_name()
        self._current_temperature = self.unit.get_current_temperature()

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
