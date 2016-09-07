"""
Support for Vera thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.util import convert
from homeassistant.components.climate import ClimateDevice
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


# pylint: disable=abstract-method
class VeraThermostat(VeraDevice, ClimateDevice):
    """Representation of a Vera Thermostat."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller)
        self._fan_list = ["On", "Auto", "Cycle"]
        self._operation_list = ["Heat", "Cool", "Auto Changeover", "Off"]

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        mode = self.vera_device.get_hvac_mode()
        if mode == "HeatOn":
            return self._operation_list[0]  # heat
        elif mode == "CoolOn":
            return self._operation_list[1]  # cool
        elif mode == "AutoChangeOver":
            return self._operation_list[2]  # auto
        elif mode == "Off":
            return self._operation_list[3]  # off
        return "Off"

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        mode = self.vera_device.get_fan_mode()
        if mode == "ContinuousOn":
            return self._fan_list[0]  # on
        elif mode == "Auto":
            return self._fan_list[1]  # auto
        elif mode == "PeriodicOn":
            return self._fan_list[2]  # cycle
        return "Auto"

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    def set_fan_mode(self, mode):
        """Set new target temperature."""
        if mode == self._fan_list[0]:
            self.vera_device.fan_on()
        elif mode == self._fan_list[1]:
            self.vera_device.fan_auto()
        elif mode == self._fan_list[2]:
            return self.vera_device.fan_cycle()

    @property
    def current_power_mwh(self):
        """Current power usage in mWh."""
        power = self.vera_device.power
        if power:
            return convert(power, float, 0.0) * 1000

    def update(self):
        """Called by the vera device callback to update state."""
        self._state = self.vera_device.get_hvac_mode()

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

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode (auto, cool, heat, off)."""
        if operation_mode == self._operation_list[3]:  # off
            self.vera_device.turn_off()
        elif operation_mode == self._operation_list[2]:  # auto
            self.vera_device.turn_auto_on()
        elif operation_mode == self._operation_list[1]:  # cool
            self.vera_device.turn_cool_on()
        elif operation_mode == self._operation_list[0]:  # heat
            self.vera_device.turn_heat_on()

    def turn_fan_on(self):
        """Turn fan on."""
        self.vera_device.fan_on()

    def turn_fan_off(self):
        """Turn fan off."""
        self.vera_device.fan_auto()
