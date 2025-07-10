"""Support for Subaru device tracker."""

from __future__ import annotations

from typing import Any

from subarulink.const import LATITUDE, LONGITUDE, TIMESTAMP

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_device_info
from .const import (
    DOMAIN,
    ENTRY_COORDINATOR,
    ENTRY_VEHICLES,
    VEHICLE_HAS_REMOTE_SERVICE,
    VEHICLE_STATUS,
    VEHICLE_VIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Subaru device tracker by config_entry."""
    entry: dict = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: DataUpdateCoordinator = entry[ENTRY_COORDINATOR]
    vehicle_info: dict = entry[ENTRY_VEHICLES]
    async_add_entities(
        SubaruDeviceTracker(vehicle, coordinator)
        for vehicle in vehicle_info.values()
        if vehicle[VEHICLE_HAS_REMOTE_SERVICE]
    )


class SubaruDeviceTracker(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], TrackerEntity
):
    """Class for Subaru device tracker."""

    _attr_translation_key = "location"
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, vehicle_info: dict, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self.vin = vehicle_info[VEHICLE_VIN]
        self._attr_device_info = get_device_info(vehicle_info)
        self._attr_unique_id = f"{self.vin}_location"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        return {
            "Position timestamp": self.coordinator.data[self.vin][VEHICLE_STATUS].get(
                TIMESTAMP
            )
        }

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the vehicle."""
        return self.coordinator.data[self.vin][VEHICLE_STATUS].get(LATITUDE)

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the vehicle."""
        return self.coordinator.data[self.vin][VEHICLE_STATUS].get(LONGITUDE)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if vehicle_data := self.coordinator.data.get(self.vin):
            if status := vehicle_data.get(VEHICLE_STATUS):
                return status.keys() & {LATITUDE, LONGITUDE, TIMESTAMP}
        return False
