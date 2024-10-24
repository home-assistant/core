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
    entities: list[IturanDeviceTracker] = [
        IturanDeviceTracker(coordinator, license_plate)
        for license_plate in coordinator.data
    ]
    async_add_entities(entities)


class IturanDeviceTracker(IturanBaseEntity, TrackerEntity):
    """Ituran device tracker."""

    _attr_force_update = False
    _attr_translation_key = "car"
    _attr_icon = "mdi:car"

    def __init__(
        self,
        coordinator: IturanDataUpdateCoordinator,
        license_plate: str,
    ) -> None:
        """Initialize the Tracker."""
        super().__init__(coordinator, license_plate)

        self._attr_unique_id = license_plate
        self._attr_name = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            ATTR_ADDRESS: self._vehicle.address,
            ATTR_HEADING: self._vehicle.heading,
            ATTR_LAST_UPDATE: self._vehicle.last_update,
        }

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._vehicle.gps_coordinates[0]

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._vehicle.gps_coordinates[1]
