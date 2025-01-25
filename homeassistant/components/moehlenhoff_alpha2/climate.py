"""Support for Alpha2 room control unit via Alpha2 base."""

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PRESET_AUTO, PRESET_DAY, PRESET_NIGHT
from .coordinator import Alpha2BaseCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Alpha2Climate entities from a config_entry."""

    coordinator: Alpha2BaseCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Alpha2Climate(coordinator, heat_area_id)
        for heat_area_id in coordinator.data["heat_areas"]
    )


class Alpha2Climate(CoordinatorEntity[Alpha2BaseCoordinator], ClimateEntity):
    """Alpha2 ClimateEntity."""

    target_temperature_step = 0.2

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_preset_modes = [PRESET_AUTO, PRESET_DAY, PRESET_NIGHT]

    def __init__(self, coordinator: Alpha2BaseCoordinator, heat_area_id: str) -> None:
        """Initialize Alpha2 ClimateEntity."""
        super().__init__(coordinator)
        self.heat_area_id = heat_area_id
        self._attr_unique_id = heat_area_id
        self._attr_name = self.heat_area["HEATAREA_NAME"]

    @property
    def heat_area(self) -> dict[str, Any]:
        """Return the heat area."""
        return self.coordinator.data["heat_areas"][self.heat_area_id]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return float(self.heat_area.get("T_TARGET_MIN", 0.0))

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return float(self.heat_area.get("T_TARGET_MAX", 30.0))

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self.heat_area.get("T_ACTUAL", 0.0))

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current hvac mode."""
        if self.coordinator.get_cooling():
            return HVACMode.COOL
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.coordinator.async_set_cooling(hvac_mode == HVACMode.COOL)

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        if not self.heat_area["_HEATCTRL_STATE"]:
            return HVACAction.IDLE
        if self.coordinator.get_cooling():
            return HVACAction.COOLING
        return HVACAction.HEATING

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return float(self.heat_area.get("T_TARGET", 0.0))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (target_temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.coordinator.async_set_target_temperature(
            self.heat_area_id, target_temperature
        )

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        if self.heat_area["HEATAREA_MODE"] == 1:
            return PRESET_DAY
        if self.heat_area["HEATAREA_MODE"] == 2:
            return PRESET_NIGHT
        return PRESET_AUTO

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new operation mode."""
        heat_area_mode = 0
        if preset_mode == PRESET_DAY:
            heat_area_mode = 1
        elif preset_mode == PRESET_NIGHT:
            heat_area_mode = 2

        await self.coordinator.async_set_heat_area_mode(
            self.heat_area_id, heat_area_mode
        )
