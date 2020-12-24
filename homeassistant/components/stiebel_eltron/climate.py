"""Support for stiebel_eltron climate platform."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_ECO,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import DOMAIN as STE_DOMAIN

DEPENDENCIES = ["stiebel_eltron"]

_LOGGER = logging.getLogger(__name__)

PRESET_DAY = "day"
PRESET_SETBACK = "setback"
PRESET_EMERGENCY = "emergency"

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_HVAC = [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]
SUPPORT_PRESET = [PRESET_ECO, PRESET_DAY, PRESET_EMERGENCY, PRESET_SETBACK]

# Mapping STIEBEL ELTRON states to homeassistant states/preset.
STE_TO_HA_HVAC = {
    "AUTOMATIC": HVAC_MODE_AUTO,
    "MANUAL MODE": HVAC_MODE_HEAT,
    "STANDBY": HVAC_MODE_AUTO,
    "DAY MODE": HVAC_MODE_AUTO,
    "SETBACK MODE": HVAC_MODE_AUTO,
    "DHW": HVAC_MODE_OFF,
    "EMERGENCY OPERATION": HVAC_MODE_AUTO,
}

STE_TO_HA_PRESET = {
    "STANDBY": PRESET_ECO,
    "DAY MODE": PRESET_DAY,
    "SETBACK MODE": PRESET_SETBACK,
    "EMERGENCY OPERATION": PRESET_EMERGENCY,
}

HA_TO_STE_HVAC = {
    HVAC_MODE_AUTO: "AUTOMATIC",
    HVAC_MODE_HEAT: "MANUAL MODE",
    HVAC_MODE_OFF: "DHW",
}

HA_TO_STE_PRESET = {k: i for i, k in STE_TO_HA_PRESET.items()}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the StiebelEltron platform."""
    name = hass.data[STE_DOMAIN]["name"]
    ste_data = hass.data[STE_DOMAIN]["ste_data"]

    add_entities([StiebelEltron(name, ste_data)], True)


class StiebelEltron(ClimateEntity):
    """Representation of a STIEBEL ELTRON heat pump."""

    def __init__(self, name, ste_data):
        """Initialize the unit."""
        self._name = name
        self._target_temperature = None
        self._current_temperature = None
        self._current_humidity = None
        self._operation = None
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
        self._operation = self._ste_data.api.get_operation()

        _LOGGER.debug(
            "Update %s, current temp: %s", self._name, self._current_temperature
        )

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {"filter_alarm": self._filter_alarm}

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

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return float(f"{self._current_humidity:.1f}")

    @property
    def hvac_modes(self):
        """List of the operation modes."""
        return SUPPORT_HVAC

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return STE_TO_HA_HVAC.get(self._operation)

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return STE_TO_HA_PRESET.get(self._operation)

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    def set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        if self.preset_mode:
            return
        new_mode = HA_TO_STE_HVAC.get(hvac_mode)
        _LOGGER.debug("set_hvac_mode: %s -> %s", self._operation, new_mode)
        self._ste_data.api.set_operation(new_mode)
        self._force_update = True

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is not None:
            _LOGGER.debug("set_temperature: %s", target_temperature)
            self._ste_data.api.set_target_temp(target_temperature)
            self._force_update = True

    def set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        new_mode = HA_TO_STE_PRESET.get(preset_mode)
        _LOGGER.debug("set_hvac_mode: %s -> %s", self._operation, new_mode)
        self._ste_data.api.set_operation(new_mode)
        self._force_update = True
