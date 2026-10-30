"""Support for Škoda device trackers."""

from typing import override

from skoda_public_api.models.enums import VehicleCapability
from skoda_public_api.models.parking_position import GPRCoordinates

from homeassistant.components.device_tracker import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaUpdateCoordinator
from .entity import SkodaEntity

PARALLEL_UPDATES = 0

PARKING_POSITION_DESCRIPTION = TrackerEntityDescription(key="parking_position")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Škoda device tracker from a config entry."""
    coordinator = entry.runtime_data.coordinator
    capabilities = coordinator.data.vehicle_response.supported_capabilities()

    if VehicleCapability.PARKING_POSITION in capabilities:
        async_add_entities([SkodaDeviceTracker(coordinator)])


class SkodaDeviceTracker(SkodaEntity, TrackerEntity):
    """Tracks the parking position of a Škoda vehicle."""

    entity_description = PARKING_POSITION_DESCRIPTION
    _attr_name = None

    def __init__(self, coordinator: SkodaUpdateCoordinator) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, coordinator.vin)

    @property
    def _gps_coordinates(self) -> GPRCoordinates | None:
        """Return the GPS coordinates of the parked vehicle."""
        if parking_position := self.open_api_vehicle.parking_position:
            return parking_position.gps_coordinates
        return None

    @property
    @override
    def latitude(self) -> float | None:
        """Return the latitude of the parked vehicle."""
        coordinates = self._gps_coordinates
        return coordinates.latitude if coordinates else None

    @property
    @override
    def longitude(self) -> float | None:
        """Return the longitude of the parked vehicle."""
        coordinates = self._gps_coordinates
        return coordinates.longitude if coordinates else None
