"""Support for Vera thermostats."""
import logging

from homeassistant.components.climate import ENTITY_ID_FORMAT, ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, STATE_ON, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.util import convert

from . import VERA_CONTROLLER, VERA_DEVICES, VeraDevice

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)

OPERATION_LIST = [STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_OFF]
FAN_OPERATION_LIST = [STATE_ON, STATE_AUTO]

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                 SUPPORT_FAN_MODE)


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up of Vera thermostats."""
    add_entities_callback(
        [VeraThermostat(device, hass.data[VERA_CONTROLLER]) for
         device in hass.data[VERA_DEVICES]['climate']], True)


class VeraThermostat(VeraDevice, ClimateDevice):
    """Representation of a Vera Thermostat."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        mode = self.vera_device.get_hvac_mode()
        if mode == 'HeatOn':
            return OPERATION_LIST[0]  # Heat
        if mode == 'CoolOn':
            return OPERATION_LIST[1]  # Cool
        if mode == 'AutoChangeOver':
            return OPERATION_LIST[2]  # Auto
        if mode == 'Off':
            return OPERATION_LIST[3]  # Off
        return 'Off'

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        mode = self.vera_device.get_fan_mode()
        if mode == "ContinuousOn":
            return FAN_OPERATION_LIST[0]  # on
        if mode == "Auto":
            return FAN_OPERATION_LIST[1]  # auto
        return "Auto"

    @property
    def fan_list(self):
        """Return a list of available fan modes."""
        return FAN_OPERATION_LIST

    def set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        if fan_mode == FAN_OPERATION_LIST[0]:
            self.vera_device.fan_on()
        else:
            self.vera_device.fan_auto()

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        power = self.vera_device.power
        if power:
            return convert(power, float, 0.0)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        vera_temp_units = (
            self.vera_device.vera_controller.temperature_units)

        if vera_temp_units == 'F':
            return TEMP_FAHRENHEIT

        return TEMP_CELSIUS

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

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self.vera_device.set_temperature(kwargs.get(ATTR_TEMPERATURE))

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode (auto, cool, heat, off)."""
        if operation_mode == OPERATION_LIST[3]:  # off
            self.vera_device.turn_off()
        elif operation_mode == OPERATION_LIST[2]:  # auto
            self.vera_device.turn_auto_on()
        elif operation_mode == OPERATION_LIST[1]:  # cool
            self.vera_device.turn_cool_on()
        elif operation_mode == OPERATION_LIST[0]:  # heat
            self.vera_device.turn_heat_on()

    def turn_fan_on(self):
        """Turn fan on."""
        self.vera_device.fan_on()

    def turn_fan_off(self):
        """Turn fan off."""
        self.vera_device.fan_auto()
