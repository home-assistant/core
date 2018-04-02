"""
Platform for Roth Touchline heat pump controller.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.touchline/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE)
from homeassistant.const import CONF_HOST, TEMP_CELSIUS, ATTR_TEMPERATURE
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pytouchline==0.7']

STATE_NORMAL = 'Normal'
STATE_NIGHT = 'Night'
STATE_VACATION = 'Holiday'
STATE_P1 = 'Pro 1'
STATE_P2 = 'Pro 2'
STATE_P3 = 'Pro 3'

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Touchline thermostats."""
    from pytouchline import PyTouchline
    host = config[CONF_HOST]
    py_touchline = PyTouchline()
    number_of_devices = int(py_touchline.get_number_of_devices(host))
    devices = []
    for device_id in range(0, number_of_devices):
        devices.append(Touchline(PyTouchline(device_id)))
    add_devices(devices, True)


class Touchline(ClimateDevice):
    """Representation of a Touchline device."""

    def __init__(self, touchline_thermostat):
        """Initialize the thermostat."""
        self.unit = touchline_thermostat
        self._name = None
        self._current_temperature = None
        self._target_temperature = None
        self._current_operation = None
        self._current_week_program = None
        self._operation_list = [STATE_NORMAL, STATE_NIGHT,
                                STATE_VACATION, STATE_P1, STATE_P2, STATE_P3]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update thermostat attributes."""
        self.unit.update()
        self._name = self.unit.get_name()
        self._current_temperature = self.unit.get_current_temperature()
        self._target_temperature = self.unit.get_target_temperature()
        self._current_operation = self.unit.get_operation_mode()
        self._current_week_program = self.unit.get_week_program()
        self._current_operation = self._current_operation

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return the current operation mode."""
        return self.map_mode_touchline_hass(self._current_operation,
                                            self._current_week_program)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def current_week_program(self):
        """Return the current week program."""
        return self._current_week_program

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.unit.set_target_temperature(self._target_temperature)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode and week program."""
        mode = self.map_mode_hass_touchline(operation_mode)
        program = self.map_program_hass_touchline(operation_mode)
        self.unit.set_operation_mode(mode)
        self.unit.set_week_program(program)
        self._current_operation = mode
        self._current_week_program = program

    @staticmethod
    def map_mode_hass_touchline(operation_mode):
        """Map Home Assistant Operation Modes to Touchline Operation Modes."""
        if operation_mode == STATE_NORMAL:
            mode = 0
        elif operation_mode == STATE_NIGHT:
            mode = 1
        elif operation_mode == STATE_VACATION:
            mode = 2
        else:
            mode = 0

        return mode

    @staticmethod
    def map_program_hass_touchline(operation_mode):
        """Map Home Assistant Operation Modes to Touchline Program Modes."""
        if operation_mode == STATE_P1:
            program = 1
        elif operation_mode == STATE_P2:
            program = 2
        elif operation_mode == STATE_P3:
            program = 3
        else:
            program = 0

        return program

    @staticmethod
    def map_mode_touchline_hass(mode, program):
        """Map Touchline Operation Modes to Home Assistant Operation Modes."""
        if mode == 0 and program == 0:
            operation_mode = STATE_NORMAL
        elif mode == 1 and program == 0:
            operation_mode = STATE_NIGHT
        elif mode == 2 and program == 0:
            operation_mode = STATE_VACATION
        elif mode == 0 and program == 1:
            operation_mode = STATE_P1
        elif mode == 0 and program == 2:
            operation_mode = STATE_P2
        elif mode == 0 and program == 3:
            operation_mode = STATE_P3
        else:
            operation_mode = None

        return operation_mode

