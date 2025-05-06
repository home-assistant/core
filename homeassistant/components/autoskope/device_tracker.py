"""Support for Autoskope device tracking."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AutoskopeDataUpdateCoordinator
from .models import AutoskopeConfigEntry, Vehicle

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutoskopeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Autoskope device tracker entities."""
    coordinator: AutoskopeDataUpdateCoordinator = entry.runtime_data.coordinator
    tracked_vehicles: set[str] = set()

    @callback
    def update_entities() -> None:
        """Update entities based on coordinator data."""
        new_entities = []
        current_vehicles = set(coordinator.data.keys()) if coordinator.data else set()

        vehicles_to_add = [
            vehicle_id
            for vehicle_id in current_vehicles - tracked_vehicles
            if coordinator.data and vehicle_id in coordinator.data
        ]

        for vehicle_id in vehicles_to_add:
            new_entities.append(AutoskopeDeviceTracker(coordinator, vehicle_id))
            tracked_vehicles.add(vehicle_id)

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(update_entities))
    update_entities()


class AutoskopeDeviceTracker(
    CoordinatorEntity[AutoskopeDataUpdateCoordinator], TrackerEntity
):
    """Representation of an Autoskope tracked device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: AutoskopeDataUpdateCoordinator, vehicle_id: str
    ) -> None:
        """Initialize the TrackerEntity."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._vehicle_id}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        vehicle_data = (
            self.coordinator.data.get(self._vehicle_id)
            if self.coordinator.data
            else None
        )

        if vehicle_data:
            return DeviceInfo(
                identifiers={(DOMAIN, str(vehicle_data.id))},
                name=vehicle_data.name,
                manufacturer=MANUFACTURER,
                model=vehicle_data.model,
                sw_version=vehicle_data.imei,
            )
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._vehicle_id))},
            name=f"Autoskope Vehicle {self._vehicle_id}",
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._vehicle_id in self.coordinator.data
        )

    @property
    def _vehicle_data(self) -> Vehicle | None:
        """Return the vehicle data for the current entity."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._vehicle_id)
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if (vehicle := self._vehicle_data) and vehicle.position:
            return vehicle.position.latitude
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if (vehicle := self._vehicle_data) and vehicle.position:
            return vehicle.position.longitude
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    def gps_accuracy(self) -> float | None:
        """Return the GPS accuracy of the device in meters."""
        if (vehicle := self._vehicle_data) and vehicle.gps_quality is not None:
            if vehicle.gps_quality > 0:
                return max(1.0, vehicle.gps_quality * 5.0)
        return None

    @property
    def icon(self) -> str:
        """Return the icon based on the vehicle's activity."""
        if (vehicle := self._vehicle_data) and vehicle.position:
            if not vehicle.position.park_mode and vehicle.position.speed > 0:
                return "mdi:car-arrow-right"
        return "mdi:car-clock"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        attrs: dict[str, Any] = {
            "battery_voltage": None,
            "external_voltage": None,
            "gps_quality": None,
            "imei": None,
            "model": None,
            "gps_accuracy": self.gps_accuracy,
            "speed": None,
            "park_mode": None,
            "last_update": None,
            "activity": "unknown",
        }
        if vehicle := self._vehicle_data:
            attrs.update(
                {
                    "battery_voltage": vehicle.battery_voltage,
                    "external_voltage": vehicle.external_voltage,
                    "gps_quality": vehicle.gps_quality,
                    "imei": vehicle.imei,
                    "model": vehicle.model,
                }
            )
            if vehicle.position:
                attrs.update(
                    {
                        "speed": vehicle.position.speed,
                        "park_mode": vehicle.position.park_mode,
                        "last_update": vehicle.position.timestamp,
                        "activity": (
                            "moving"
                            if not vehicle.position.park_mode
                            and vehicle.position.speed > 0
                            else "parked"
                        ),
                    }
                )
        return attrs
