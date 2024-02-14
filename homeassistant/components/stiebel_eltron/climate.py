"""Support for stiebel_eltron climate platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as STE_DOMAIN

DEPENDENCIES = ["stiebel_eltron"]

_LOGGER = logging.getLogger(__name__)

PRESET_DAY = "day"
PRESET_SETBACK = "setback"
PRESET_EMERGENCY = "emergency"

SUPPORT_HVAC = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
SUPPORT_PRESET = [PRESET_ECO, PRESET_DAY, PRESET_EMERGENCY, PRESET_SETBACK]

# Mapping STIEBEL ELTRON states to homeassistant states/preset.
STE_TO_HA_HVAC = {
    "AUTOMATIC": HVACMode.AUTO,
    "MANUAL MODE": HVACMode.HEAT,
    "STANDBY": HVACMode.AUTO,
    "DAY MODE": HVACMode.AUTO,
    "SETBACK MODE": HVACMode.AUTO,
    "DHW": HVACMode.OFF,
    "EMERGENCY OPERATION": HVACMode.AUTO,
}

STE_TO_HA_PRESET = {
    "STANDBY": PRESET_ECO,
    "DAY MODE": PRESET_DAY,
    "SETBACK MODE": PRESET_SETBACK,
    "EMERGENCY OPERATION": PRESET_EMERGENCY,
}

HA_TO_STE_HVAC = {
    HVACMode.AUTO: "AUTOMATIC",
    HVACMode.HEAT: "MANUAL MODE",
    HVACMode.OFF: "DHW",
}

HA_TO_STE_PRESET = {k: i for i, k in STE_TO_HA_PRESET.items()}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the StiebelEltron platform."""
    name = hass.data[STE_DOMAIN]["name"]
    ste_data = hass.data[STE_DOMAIN]["ste_data"]

    add_entities([StiebelEltron(name, ste_data)], True)


class StiebelEltron(ClimateEntity):
    """Representation of a STIEBEL ELTRON heat pump."""

    _attr_hvac_modes = SUPPORT_HVAC
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

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

    def update(self) -> None:
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
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {"filter_alarm": self._filter_alarm}

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    # Handle ClimateEntityFeature.TARGET_TEMPERATURE

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
    def hvac_mode(self) -> HVACMode | None:
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

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if self.preset_mode:
            return
        new_mode = HA_TO_STE_HVAC.get(hvac_mode)
        _LOGGER.debug("set_hvac_mode: %s -> %s", self._operation, new_mode)
        self._ste_data.api.set_operation(new_mode)
        self._force_update = True

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is not None:
            _LOGGER.debug("set_temperature: %s", target_temperature)
            self._ste_data.api.set_target_temp(target_temperature)
            self._force_update = True

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        new_mode = HA_TO_STE_PRESET.get(preset_mode)
        _LOGGER.debug("set_hvac_mode: %s -> %s", self._operation, new_mode)
        self._ste_data.api.set_operation(new_mode)
        self._force_update = True
