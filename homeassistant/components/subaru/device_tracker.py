"""Support for Subaru device tracker."""
from __future__ import annotations

from typing import Any

import subarulink.const as sc

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Subaru device tracker by config_entry."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry[ENTRY_COORDINATOR]
    vehicle_info = entry[ENTRY_VEHICLES]
    entities = []
    for info in vehicle_info.values():
        if info[VEHICLE_HAS_REMOTE_SERVICE]:
            entities.append(SubaruDeviceTracker(info, coordinator))
    async_add_entities(entities)


class SubaruDeviceTracker(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], TrackerEntity
):
    """Class for Subaru device tracker."""

    _attr_icon = "mdi:car"
    _attr_has_entity_name = True
    name = "Location"

    def __init__(self, vehicle_info: dict, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self.vin = vehicle_info[VEHICLE_VIN]
        self._attr_device_info = get_device_info(vehicle_info)
        self._attr_unique_id = f"{self.vin}_location"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        extra_attributes = None
        if self.vin in self.coordinator.data:
            extra_attributes = {
                "Position timestamp": self.coordinator.data[self.vin][
                    VEHICLE_STATUS
                ].get(sc.POSITION_TIMESTAMP)
            }
        return extra_attributes

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the vehicle."""
        latitude = None
        if self.vin in self.coordinator.data:
            latitude = self.coordinator.data[self.vin][VEHICLE_STATUS].get(sc.LATITUDE)
        return latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the vehicle."""
        longitude = None
        if self.vin in self.coordinator.data:
            longitude = self.coordinator.data[self.vin][VEHICLE_STATUS].get(
                sc.LONGITUDE
            )
        return longitude

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the vehicle."""
        return SourceType.GPS
