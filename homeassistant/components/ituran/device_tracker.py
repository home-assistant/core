"""Device tracker for Ituran vehicles."""

from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IturanConfigEntry
from .coordinator import IturanDataUpdateCoordinator
from .entity import IturanBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IturanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ituran tracker from config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        IturanDeviceTracker(coordinator, license_plate)
        for license_plate in coordinator.data
    )


class IturanDeviceTracker(IturanBaseEntity, TrackerEntity):
    """Ituran device tracker."""

    _attr_translation_key = "car"
    _attr_name = None

    def __init__(
        self,
        coordinator: IturanDataUpdateCoordinator,
        license_plate: str,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, license_plate, "device_tracker")

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.vehicle.gps_coordinates[0]

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.vehicle.gps_coordinates[1]
