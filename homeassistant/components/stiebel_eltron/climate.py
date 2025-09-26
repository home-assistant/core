"""Support for stiebel_eltron climate platform."""

from __future__ import annotations

import logging
from typing import Any

from pystiebeleltron.pystiebeleltron import StiebelEltronAPI

from homeassistant.components.climate import (
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import StiebelEltronConfigEntry

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StiebelEltronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STIEBEL ELTRON climate platform."""

    async_add_entities([StiebelEltron(entry.title, entry.runtime_data)], True)


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

    def __init__(self, name: str, client: StiebelEltronAPI) -> None:
        """Initialize the unit."""
        self._name = name
        self._target_temperature: float | int | None = None
        self._current_temperature: float | int | None = None
        self._current_humidity: float | int | None = None
        self._operation: str | None = None
        self._filter_alarm: bool | None = None
        self._client = client

    def update(self) -> None:
        """Update unit attributes."""
        self._client.update()

        self._target_temperature = self._client.get_target_temp()
        self._current_temperature = self._client.get_current_temp()
        self._current_humidity = self._client.get_current_humidity()
        self._filter_alarm = self._client.get_filter_alarm_status()
        self._operation = self._client.get_operation()

        _LOGGER.debug(
            "Update %s, current temp: %s", self._name, self._current_temperature
        )

    @property
    def extra_state_attributes(self) -> dict[str, bool | None]:
        """Return device specific state attributes."""
        return {"filter_alarm": self._filter_alarm}

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._name

    # Handle ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 0.1

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 10.0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 30.0

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return float(f"{self._current_humidity:.1f}")

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation ie. heat, cool, idle."""
        return STE_TO_HA_HVAC.get(self._operation) if self._operation else None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return STE_TO_HA_PRESET.get(self._operation) if self._operation else None

    @property
    def preset_modes(self) -> list[str]:
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if self.preset_mode:
            return
        new_mode = HA_TO_STE_HVAC.get(hvac_mode)
        _LOGGER.debug("set_hvac_mode: %s -> %s", self._operation, new_mode)
        self._client.set_operation(new_mode)

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is not None:
            _LOGGER.debug("set_temperature: %s", target_temperature)
            self._client.set_target_temp(target_temperature)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        new_mode = HA_TO_STE_PRESET.get(preset_mode)
        _LOGGER.debug("set_hvac_mode: %s -> %s", self._operation, new_mode)
        self._client.set_operation(new_mode)
