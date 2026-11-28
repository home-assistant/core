"""Support for SleepIQ switches."""

from typing import Any, override

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import RESPONSIVE_AIR
from .coordinator import SleepIQConfigEntry, SleepIQPauseUpdateCoordinator
from .entity import SleepIQBedEntity, SleepIQSleeperEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SleepIQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sleep number switches."""
    data = entry.runtime_data
    coordinator = data.pause_coordinator
    entities: list[SwitchEntity] = [
        SleepNumberPrivateSwitch(coordinator, bed) for bed in data.client.beds.values()
    ]
    entities.extend(
        SleepIQResponsiveAirSwitch(coordinator, bed, sleeper)
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        if sleeper in coordinator.responsive_air_sleepers
    )
    async_add_entities(entities)


class SleepNumberPrivateSwitch(
    SleepIQBedEntity[SleepIQPauseUpdateCoordinator], SwitchEntity
):
    """Representation of SleepIQ privacy mode."""

    def __init__(
        self, coordinator: SleepIQPauseUpdateCoordinator, bed: SleepIQBed
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, bed)
        self._attr_name = f"SleepNumber {bed.name} Pause Mode"
        self._attr_unique_id = f"{bed.id}-pause-mode"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.bed.set_pause_mode(True)
        self._handle_coordinator_update()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.bed.set_pause_mode(False)
        self._handle_coordinator_update()

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Update switch attributes."""
        self._attr_is_on = self.bed.paused


class SleepIQResponsiveAirSwitch(
    SleepIQSleeperEntity[SleepIQPauseUpdateCoordinator], SwitchEntity
):
    """Representation of SleepIQ Responsive Air for one side."""

    _attr_icon = "mdi:auto-mode"

    def __init__(
        self,
        coordinator: SleepIQPauseUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, bed, sleeper, RESPONSIVE_AIR)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Responsive Air."""
        await self.sleeper.set_responsive_air(True)
        self._handle_coordinator_update()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Responsive Air."""
        await self.sleeper.set_responsive_air(False)
        self._handle_coordinator_update()

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Update switch attributes."""
        self._attr_is_on = self.sleeper.responsive_air
