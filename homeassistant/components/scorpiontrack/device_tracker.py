"""Device tracker platform for ScorpionTrack."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ScorpionTrackConfigEntry
from .entity import ScorpionTrackEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ScorpionTrackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ScorpionTrack tracker entities."""
    coordinator = entry.runtime_data
    known_vehicle_ids: set[int] = set()

    @callback
    def _async_add_missing_entities() -> None:
        new_vehicle_ids = [
            vehicle.id
            for vehicle in coordinator.data.vehicles
            if vehicle.id not in known_vehicle_ids
        ]
        if not new_vehicle_ids:
            return

        known_vehicle_ids.update(new_vehicle_ids)
        async_add_entities(
            ScorpionTrackTrackerEntity(coordinator, vehicle_id)
            for vehicle_id in new_vehicle_ids
        )

    _async_add_missing_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_missing_entities))


class ScorpionTrackTrackerEntity(ScorpionTrackEntity, TrackerEntity):
    """Represent the latest shared GPS location for a vehicle."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:car"
    _attr_location_accuracy = 0.0
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator, vehicle_id: int) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, vehicle_id)
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}_tracker"

    @property
    def name(self) -> str:
        """Return the vehicle-facing tracker label used on the map."""
        vehicle = self.get_vehicle()
        if vehicle is None:
            return self._cached_registration or self._cached_display_name
        return vehicle.registration or vehicle.display_name

    @property
    def available(self) -> bool:
        """Return if the tracker is available."""
        vehicle = self.get_vehicle()
        return (
            super().available
            and vehicle is not None
            and vehicle.position.latitude is not None
            and vehicle.position.longitude is not None
        )

    @property
    def latitude(self) -> float | None:
        """Return the latitude."""
        vehicle = self.get_vehicle()
        if vehicle is None:
            return None
        return vehicle.position.latitude

    @property
    def longitude(self) -> float | None:
        """Return the longitude."""
        vehicle = self.get_vehicle()
        if vehicle is None:
            return None
        return vehicle.position.longitude

    @property
    def location_accuracy(self) -> float:
        """Return the location accuracy in meters."""
        return 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        vehicle = self.get_vehicle()
        position = vehicle.position if vehicle else None
        converted_speed = self.share.convert_speed(
            position.speed_kmh if position else None
        )
        attributes = self.common_location_attributes()
        attributes.update(
            {
                "speed": converted_speed,
                "speed_unit": "mph" if self.share.uses_miles else "km/h",
                "speed_kmh": position.speed_kmh if position else None,
                "distance_units": self.share.distance_units,
            }
        )
        return attributes
