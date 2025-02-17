"""Support for Renault device trackers."""

from __future__ import annotations

from dataclasses import dataclass

from renault_api.kamereon.models import KamereonVehicleLocationData

from homeassistant.components.device_tracker import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RenaultTrackerEntityDescription(
    TrackerEntityDescription, RenaultDataEntityDescription
):
    """Class describing Renault tracker entities."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    entities: list[RenaultDeviceTracker] = [
        RenaultDeviceTracker(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in DEVICE_TRACKER_TYPES
        if description.coordinator in vehicle.coordinators
    ]
    async_add_entities(entities)


class RenaultDeviceTracker(
    RenaultDataEntity[KamereonVehicleLocationData], TrackerEntity
):
    """Mixin for device tracker specific attributes."""

    entity_description: RenaultTrackerEntityDescription

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.coordinator.data.gpsLatitude if self.coordinator.data else None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.coordinator.data.gpsLongitude if self.coordinator.data else None


DEVICE_TRACKER_TYPES: tuple[RenaultTrackerEntityDescription, ...] = (
    RenaultTrackerEntityDescription(
        key="location",
        coordinator="location",
        translation_key="location",
    ),
)
