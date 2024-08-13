"""Entity for the SleepIQ integration."""

from abc import abstractmethod

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ENTITY_TYPES, ICON_OCCUPIED
from .coordinator import SleepIQDataUpdateCoordinator, SleepIQPauseUpdateCoordinator

type _DataCoordinatorType = SleepIQDataUpdateCoordinator | SleepIQPauseUpdateCoordinator


def device_from_bed(bed: SleepIQBed) -> DeviceInfo:
    """Create a device given a bed."""
    return DeviceInfo(
        connections={(dr.CONNECTION_NETWORK_MAC, bed.mac_addr)},
        manufacturer="SleepNumber",
        name=bed.name,
        model=bed.model,
    )


def sleeper_for_side(bed: SleepIQBed, side: str) -> SleepIQSleeper:
    """Find the sleeper for a side or the first sleeper."""
    for sleeper in bed.sleepers:
        if sleeper.side == side:
            return sleeper
    return bed.sleepers[0]


class SleepIQEntity(Entity):
    """Implementation of a SleepIQ entity."""

    def __init__(self, bed: SleepIQBed) -> None:
        """Initialize the SleepIQ entity."""
        self.bed = bed
        self._attr_device_info = device_from_bed(bed)


class SleepIQBedEntity[_SleepIQCoordinatorT: _DataCoordinatorType](
    CoordinatorEntity[_SleepIQCoordinatorT]
):
    """Implementation of a SleepIQ sensor."""

    _attr_icon = ICON_OCCUPIED

    def __init__(
        self,
        coordinator: _SleepIQCoordinatorT,
        bed: SleepIQBed,
    ) -> None:
        """Initialize the SleepIQ sensor entity."""
        super().__init__(coordinator)
        self.bed = bed
        self._attr_device_info = device_from_bed(bed)
        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""


class SleepIQSleeperEntity[_SleepIQCoordinatorT: _DataCoordinatorType](
    SleepIQBedEntity[_SleepIQCoordinatorT]
):
    """Implementation of a SleepIQ sensor."""

    _attr_icon = ICON_OCCUPIED

    def __init__(
        self,
        coordinator: _SleepIQCoordinatorT,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
        name: str,
    ) -> None:
        """Initialize the SleepIQ sensor entity."""
        self.sleeper = sleeper
        super().__init__(coordinator, bed)

        self._attr_name = f"SleepNumber {bed.name} {sleeper.name} {ENTITY_TYPES[name]}"
        self._attr_unique_id = f"{sleeper.sleeper_id}_{name}"
