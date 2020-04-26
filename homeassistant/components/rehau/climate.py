"""The Rehau Nea Smart Manager integration."""
import voluptuous as vol
from pyrehau_neasmart import RehauNeaSmart

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_PRESET_MODE,
    PRESET_ECO,
    PRESET_COMFORT,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)

import homeassistant.helpers.config_validation as cv

import logging

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

PRESET_AUTO = "auto"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Rehau NeaSmart thermostats."""
    host = config.get(CONF_HOST)

    rehau = RehauNeaSmart(host)

    heatareas = rehau.heatareas()
    for heatarea in heatareas:
        add_entities([RehauThermostat(heatarea)], True)


class RehauThermostat(ClimateDevice):
    """Rehau Theromstat class."""

    def __init__(self, ha):
        """Initialize the thermostat."""
        self._heatarea = ha
        self._name = self._heatarea.heatarea_name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """Set up polling needed for thermostat."""
        return True

    def update(self):
        """Update the data from the thermostat."""
        self._heatarea.update_status()

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def precision(self):
        """Return the precision of the system.

        Proliphix temperature values are passed back and forth in the
        API as tenths of degrees F (i.e. 690 for 69 degrees).
        """
        return PRECISION_TENTHS

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {}

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return float(self._heatarea.t_actual)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self._heatarea.t_target)

    @property
    def hvac_mode(self):
        """Return the current state of the thermostat."""
        """Return the current state of the thermostat."""
        state = int(self._heatarea.heatarea_mode)
        if state == 0:
            return PRESET_AUTO
        if state == 1:
            return PRESET_COMFORT
        if state == 2:
            return PRESET_ECO

    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        return []

    @property
    def preset_mode(self):
        """Return the current state of the thermostat."""
        state = int(self._heatarea.heatarea_mode)
        if state == 0:
            return PRESET_AUTO
        if state == 1:
            return PRESET_COMFORT
        if state == 2:
            return PRESET_ECO

    @property
    def preset_modes(self):
        """Return available HVAC modes."""
        return [
            PRESET_ECO,
            PRESET_COMFORT,
            PRESET_AUTO,
        ]

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        print(temperature)
        self._heatarea.set_t_target(float(temperature))

    def set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        if preset_mode == "eco":
            preset_mode_value = 2
        elif preset_mode == "comfort":
            preset_mode_value = 1
        elif preset_mode == "auto":
            preset_mode_value = 0
        else:
            return False

        self._heatarea.set_heatarea_mode(preset_mode_value)
