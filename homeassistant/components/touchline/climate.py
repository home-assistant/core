"""
Platform for Roth Touchline floor heating controller.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/touchline/
"""
import logging

from typing import List

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA

from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE, HVAC_MODE_HEAT)

from homeassistant.const import CONF_HOST, TEMP_CELSIUS, ATTR_TEMPERATURE

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PRESET_NORMAL = 'Normal'
PRESET_NIGHT = 'Night'
PRESET_VACATION = 'Holiday'
PRESET_P1 = 'Pro 1'
PRESET_P2 = 'Pro 2'
PRESET_P3 = 'Pro 3'

PRESET_MODES = [
    PRESET_NORMAL,
    PRESET_NIGHT,
    PRESET_VACATION,
    PRESET_P1,
    PRESET_P2,
    PRESET_P3
]

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Touchline devices."""
    from pytouchline import PyTouchline
    host = config[CONF_HOST]
    py_touchline = PyTouchline()
    number_of_devices = int(py_touchline.get_number_of_devices(host))
    devices = []
    for device_id in range(0, number_of_devices):
        devices.append(Touchline(PyTouchline(device_id)))
    add_entities(devices, True)


class Touchline(ClimateDevice):
    """Representation of a Touchline device."""

    def __init__(self, touchline_thermostat):
        """Initialize the Touchline device."""
        self.unit = touchline_thermostat
        self._name = None
        self._current_temperature = None
        self._target_temperature = None
        self._current_operation_mode = None
        self._current_week_program = None
        self._preset_mode = None
        self._preset_modes = PRESET_MODES

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
        self._current_operation_mode = self.unit.get_operation_mode()
        self._current_week_program = self.unit.get_week_program()
        self._current_preset_mode = self.map_mode_touchline_hass(self._current_operation_mode, self._current_week_program)
        self._preset_mode = self.map_mode_touchline_hass(self._current_operation_mode, self._current_week_program)

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.
        Need to be one of HVAC_MODE_*."""
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.
        Need to be a subset of HVAC_MODES."""
        return [HVAC_MODE_HEAT]

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
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_operation_mode(self):
        """Return the current operation mode."""
        return self._current_operation_mode

    @property
    def current_week_program(self):
        """Return the current week program."""
        return self._current_week_program

    @property
    def current_preset_mode(self):
        """Return the current preset mode."""
        return self._current_preset_mode

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return PRESET_MODES

    def set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        mode = self.map_mode_hass_touchline(preset_mode)
        program = self.map_program_hass_touchline(preset_mode)
        self.unit.set_operation_mode(mode)
        self.unit.set_week_program(program)
        self._current_operation_mode = mode
        self._current_week_program = program
        self._current_preset_mode = preset_mode

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.unit.set_target_temperature(self._target_temperature)

    @staticmethod
    def map_mode_hass_touchline(preset_mode):
        """Map Home Assistant Preset Modes to Touchline Operation Modes."""
        if preset_mode == PRESET_NORMAL:
            mode = 0
        elif preset_mode == PRESET_NIGHT:
            mode = 1
        elif preset_mode == PRESET_VACATION:
            mode = 2
        else:
            mode = 0

        return mode

    @staticmethod
    def map_program_hass_touchline(preset_mode):
        """Map Home Assistant Preset Modes to Touchline Program Modes."""
        if preset_mode == PRESET_P1:
            week_program = 1
        elif preset_mode == PRESET_P2:
            week_program = 2
        elif preset_mode == PRESET_P3:
            week_program = 3
        else:
            week_program = 0

        return week_program

    @staticmethod
    def map_mode_touchline_hass(operation_mode, week_program):
        """Map Touchline Operation Modes to Home Assistant Preset Modes."""
        if operation_mode == 0 and week_program == 0:
            preset_mode = PRESET_NORMAL
        elif operation_mode == 1 and week_program == 0:
            preset_mode = PRESET_NIGHT
        elif operation_mode == 2 and week_program == 0:
            preset_mode = PRESET_VACATION
        elif operation_mode == 0 and week_program == 1:
            preset_mode = PRESET_P1
        elif operation_mode == 0 and week_program == 2:
            preset_mode = PRESET_P2
        elif operation_mode == 0 and week_program == 3:
            preset_mode = PRESET_P3
        else:
            preset_mode = None

        return preset_mode
