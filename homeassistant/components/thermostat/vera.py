"""
Support for Vera thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.util import convert
from homeassistant.components.thermostat import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_OFF,
    ThermostatDevice)
from homeassistant.const import TEMP_FAHRENHEIT

from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return Vera thermostats."""
    add_devices_callback(
        VeraThermostat(device, VERA_CONTROLLER) for
        device in VERA_DEVICES['thermostat'])


class VeraThermostat(VeraDevice, ThermostatDevice):
    """Representation of a Vera Thermostat."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def current_power_mwh(self):
        """Current power usage in mWh."""
        power = self.vera_device.power
        if power:
            return convert(power, float, 0.0) * 1000

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.vera_device.get_current_temperature()

    @property
    def operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self.vera_device.get_hvac_state()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.vera_device.get_current_goal_temperature()

    def set_temperature(self, temperature):
        """Set new target temperature."""
        self.vera_device.set_temperature(temperature)

    def set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (auto, cool, heat, off)."""
        if hvac_mode == STATE_OFF:
            self.vera_device.turn_off()
        elif hvac_mode == STATE_AUTO:
            self.vera_device.turn_auto_on()
        elif hvac_mode == STATE_COOL:
            self.vera_device.turn_cool_on()
        elif hvac_mode == STATE_HEAT:
            self.vera_device.turn_heat_on()

    def turn_fan_on(self):
        """Turn fan on."""
        self.vera_device.fan_on()

    def turn_fan_off(self):
        """Turn fan off."""
        self.vera_device.fan_auto()
