"""Entity for the SleepIQ integration."""
from abc import abstractmethod

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.core import callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, ICON_OCCUPIED, SENSOR_TYPES


class SleepIQSensor(CoordinatorEntity):
    """Implementation of a SleepIQ sensor."""

    _attr_icon = ICON_OCCUPIED

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
        name: str,
    ) -> None:
        """Initialize the SleepIQ side entity."""
        super().__init__(coordinator)
        self.bed = bed
        self.sleeper = sleeper
        self._async_update_attrs()

        self._attr_name = f"SleepNumber {bed.name} {sleeper.name} {SENSOR_TYPES[name]}"
        self._attr_unique_id = f"{bed.id}_{sleeper.name}_{name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.bed.id)},
            connections={(device_registry.CONNECTION_NETWORK_MAC, self.bed.mac_addr)},
            manufacturer="SleepNumber",
            name=self.bed.name,
            model=self.bed.model,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
