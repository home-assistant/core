"""Support for Renault device trackers."""

from dataclasses import dataclass
from typing import override

from renault_api.kamereon.models import KamereonVehicleLocationData

from homeassistant.components.device_tracker import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription
from .renault_vehicle import RenaultVehicleProxy

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

    @callback
    def _async_add_vehicle(vehicle: RenaultVehicleProxy) -> None:
        async_add_entities(
            RenaultDeviceTracker(vehicle, description)
            for description in DEVICE_TRACKER_TYPES
            if description.coordinator in vehicle.coordinators
        )

    config_entry.async_on_unload(
        config_entry.runtime_data.async_add_vehicle_listener(_async_add_vehicle)
    )


class RenaultDeviceTracker(
    RenaultDataEntity[KamereonVehicleLocationData], TrackerEntity
):
    """Mixin for device tracker specific attributes."""

    entity_description: RenaultTrackerEntityDescription

    @property
    @override
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.coordinator.data.gpsLatitude

    @property
    @override
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.coordinator.data.gpsLongitude


DEVICE_TRACKER_TYPES: tuple[RenaultTrackerEntityDescription, ...] = (
    RenaultTrackerEntityDescription(
        key="location",
        coordinator="location",
        translation_key="location",
    ),
)
