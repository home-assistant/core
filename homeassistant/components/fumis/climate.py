"""Support for Fumis climate entities."""

from __future__ import annotations

from typing import Any

from fumis import StoveStatus

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FumisConfigEntry, FumisDataUpdateCoordinator
from .entity import FumisEntity
from .helpers import fumis_exception_handler

PARALLEL_UPDATES = 1

STOVE_STATUS_TO_HVAC_ACTION: dict[StoveStatus, HVACAction | None] = {
    StoveStatus.OFF: HVACAction.OFF,
    StoveStatus.COLD_START_OFF: HVACAction.OFF,
    StoveStatus.WOOD_BURNING_OFF: HVACAction.OFF,
    StoveStatus.PRE_HEATING: HVACAction.PREHEATING,
    StoveStatus.IGNITION: HVACAction.PREHEATING,
    StoveStatus.PRE_COMBUSTION: HVACAction.PREHEATING,
    StoveStatus.COLD_START: HVACAction.PREHEATING,
    StoveStatus.COMBUSTION: HVACAction.HEATING,
    StoveStatus.ECO: HVACAction.HEATING,
    StoveStatus.HYBRID_INIT: HVACAction.HEATING,
    StoveStatus.HYBRID_START: HVACAction.HEATING,
    StoveStatus.WOOD_START: HVACAction.HEATING,
    StoveStatus.WOOD_COMBUSTION: HVACAction.HEATING,
    StoveStatus.COOLING: HVACAction.IDLE,
    StoveStatus.UNKNOWN: None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FumisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fumis climate entity based on a config entry."""
    async_add_entities([FumisClimateEntity(entry.runtime_data)])


class FumisClimateEntity(FumisEntity, ClimateEntity):
    """Defines a Fumis climate entity."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_max_temp = 35.0
    _attr_min_temp = 10.0
    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: FumisDataUpdateCoordinator) -> None:
        """Initialize the Fumis climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.unique_id

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if self.coordinator.data.controller.on:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        return STOVE_STATUS_TO_HVAC_ACTION[
            self.coordinator.data.controller.stove_status
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if (temp := self.coordinator.data.controller.main_temperature) is None:
            return None
        return temp.actual

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if (temp := self.coordinator.data.controller.main_temperature) is None:
            return None
        return temp.setpoint

    @fumis_exception_handler
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.client.turn_on()
        else:
            await self.coordinator.client.turn_off()
        await self.coordinator.async_request_refresh()

    @fumis_exception_handler
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.coordinator.client.set_target_temperature(temperature)
        await self.coordinator.async_request_refresh()

    @fumis_exception_handler
    async def async_turn_on(self) -> None:
        """Turn on the stove."""
        await self.coordinator.client.turn_on()
        await self.coordinator.async_request_refresh()

    @fumis_exception_handler
    async def async_turn_off(self) -> None:
        """Turn off the stove."""
        await self.coordinator.client.turn_off()
        await self.coordinator.async_request_refresh()
