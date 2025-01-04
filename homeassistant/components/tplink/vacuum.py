"""Support for TPLink vacuum."""

from __future__ import annotations

from typing import Any

from kasa import Device, Module
from kasa.smart.modules.vacuum import Status, Vacuum

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after

STATUS_TO_ACTIVITY = {
    Status.Idle: VacuumActivity.IDLE,
    Status.Cleaning: VacuumActivity.CLEANING,
    Status.GoingHome: VacuumActivity.RETURNING,
    Status.Charging: VacuumActivity.DOCKED,
    Status.Charged: VacuumActivity.DOCKED,
    Status.Paused: VacuumActivity.PAUSED,
    Status.Error: VacuumActivity.ERROR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up vacuum entities."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    if Module.Vacuum in device.modules:
        async_add_entities([TPLinkVacuumEntity(device, parent_coordinator)])


class TPLinkVacuumEntity(CoordinatedTPLinkEntity, StateVacuumEntity):
    """Representation of a tplink vacuum."""

    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
    )

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
    ) -> None:
        """Initialize the vacuum entity."""
        self._vacuum_module: Vacuum = device.modules[Module.Vacuum]
        super().__init__(device, coordinator)

    @async_refresh_after
    async def async_start(self) -> None:
        """Start cleaning."""
        await self._vacuum_module.start()

    @async_refresh_after
    async def async_pause(self) -> None:
        """Pause cleaning."""
        await self._vacuum_module.pause()

    @async_refresh_after
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return home."""
        await self._vacuum_module.return_home()

    @property
    def battery_level(self) -> int | None:
        """Return battery level."""
        return self._vacuum_module.battery

    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_activity = STATUS_TO_ACTIVITY.get(self._vacuum_module.status)
        return True
