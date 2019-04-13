"""Support for stiebel_eltron climate platform."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_ECO, STATE_MANUAL, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, STATE_ON, TEMP_CELSIUS)

from . import DOMAIN as STE_DOMAIN

DEPENDENCIES = ['stiebel_eltron']

_LOGGER = logging.getLogger(__name__)


SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE
OPERATION_MODES = [STATE_AUTO, STATE_MANUAL, STATE_ECO, STATE_OFF]

# Mapping STIEBEL ELTRON states to homeassistant states.
STE_TO_HA_STATE = {'AUTOMATIC': STATE_AUTO,
                   'MANUAL MODE': STATE_MANUAL,
                   'STANDBY': STATE_ECO,
                   'DAY MODE': STATE_ON,
                   'SETBACK MODE': STATE_ON,
                   'DHW': STATE_OFF,
                   'EMERGENCY OPERATION': STATE_ON}

# Mapping homeassistant states to STIEBEL ELTRON states.
HA_TO_STE_STATE = {value: key for key, value in STE_TO_HA_STATE.items()}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the StiebelEltron platform."""
    name = hass.data[STE_DOMAIN]['name']
    ste_data = hass.data[STE_DOMAIN]['ste_data']

    add_entities([StiebelEltron(name, ste_data)], True)


class StiebelEltron(ClimateDevice):
    """Representation of a STIEBEL ELTRON heat pump."""

    def __init__(self, name, ste_data):
        """Initialize the unit."""
        self._name = name
        self._target_temperature = None
        self._current_temperature = None
        self._current_humidity = None
        self._operation_modes = OPERATION_MODES
        self._current_operation = None
        self._filter_alarm = None
        self._force_update = False
        self._ste_data = ste_data

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update unit attributes."""
        self._ste_data.update(no_throttle=self._force_update)
        self._force_update = False

        self._target_temperature = self._ste_data.api.get_target_temp()
        self._current_temperature = self._ste_data.api.get_current_temp()
        self._current_humidity = self._ste_data.api.get_current_humidity()
        self._filter_alarm = self._ste_data.api.get_filter_alarm_status()
        self._current_operation = self._ste_data.api.get_operation()

        _LOGGER.debug("Update %s, current temp: %s", self._name,
                      self._current_temperature)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            'filter_alarm': self._filter_alarm
        }

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    # Handle SUPPORT_TARGET_TEMPERATURE
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
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.1

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 10.0

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30.0

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is not None:
            _LOGGER.debug("set_temperature: %s", target_temperature)
            self._ste_data.api.set_target_temp(target_temperature)
            self._force_update = True

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return float("{0:.1f}".format(self._current_humidity))

    # Handle SUPPORT_OPERATION_MODE
    @property
    def operation_list(self):
        """List of the operation modes."""
        return self._operation_modes

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return STE_TO_HA_STATE.get(self._current_operation)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        new_mode = HA_TO_STE_STATE.get(operation_mode)
        _LOGGER.debug("set_operation_mode: %s -> %s", self._current_operation,
                      new_mode)
        self._ste_data.api.set_operation(new_mode)
        self._force_update = True
