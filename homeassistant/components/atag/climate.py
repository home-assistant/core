"""Initialization of ATAG One climate platform."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from . import DOMAIN, AtagEntity

PRESET_MAP = {
    "Manual": "manual",
    "Auto": "automatic",
    "Extend": "extend",
    PRESET_AWAY: "vacation",
    PRESET_BOOST: "fireplace",
}
PRESET_INVERTED = {v: k for k, v in PRESET_MAP.items()}
HVAC_MODES = [HVACMode.AUTO, HVACMode.HEAT]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Load a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtagThermostat(coordinator, Platform.CLIMATE)])


class AtagThermostat(AtagEntity, ClimateEntity):
    """Atag climate device."""

    _attr_hvac_modes = HVAC_MODES
    _attr_preset_modes = list(PRESET_MAP.keys())
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, atag_id):
        """Initialize an Atag climate device."""
        super().__init__(coordinator, atag_id)
        self._attr_temperature_unit = coordinator.data.climate.temp_unit

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        return try_parse_enum(HVACMode, self.coordinator.data.climate.hvac_mode)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        is_active = self.coordinator.data.climate.status
        return HVACAction.HEATING if is_active else HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.data.climate.temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.data.climate.target_temperature

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, manual, fireplace, extend, etc."""
        preset = self.coordinator.data.climate.preset_mode
        return PRESET_INVERTED.get(preset)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.coordinator.data.climate.set_temp(kwargs.get(ATTR_TEMPERATURE))
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.coordinator.data.climate.set_hvac_mode(hvac_mode)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.coordinator.data.climate.set_preset_mode(PRESET_MAP[preset_mode])
        self.async_write_ha_state()
