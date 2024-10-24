"""Device tracker for Ituran vehicles."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IturanConfigEntry
from .const import ATTR_ADDRESS, ATTR_HEADING, ATTR_LAST_UPDATE
from .coordinator import IturanDataUpdateCoordinator
from .entity import IturanBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IturanConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ituran tracker from config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        IturanDeviceTracker(coordinator, license_plate)
        for license_plate in coordinator.data
    )


class IturanDeviceTracker(IturanBaseEntity, TrackerEntity):
    """Ituran device tracker."""

    _attr_force_update = False
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            ATTR_ADDRESS: self.vehicle.address,
            ATTR_HEADING: self.vehicle.heading,
            ATTR_LAST_UPDATE: self.vehicle.last_update,
        }

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.vehicle.gps_coordinates[0]

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.vehicle.gps_coordinates[1]
