"""Device tracker platform for ScorpionTrack."""

from typing import override

from pyscorpiontrack import ScorpionTrackVehicle

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator
from .entity import ScorpionTrackEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ScorpionTrackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ScorpionTrack tracker entities."""
    coordinator = entry.runtime_data
    known_vehicles: set[int] = set()

    @callback
    def async_add_new_vehicles() -> None:
        """Add trackers for vehicles newly included in the share."""
        new_vehicles = coordinator.vehicles_by_id.keys() - known_vehicles
        if not new_vehicles:
            return
        known_vehicles.update(new_vehicles)
        async_add_entities(
            ScorpionTrackTrackerEntity(coordinator, vehicle_id)
            for vehicle_id in new_vehicles
        )

    async_add_new_vehicles()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_vehicles))


class ScorpionTrackTrackerEntity(ScorpionTrackEntity, TrackerEntity):
    """Represent the latest shared GPS location for a vehicle."""

    _attr_name = None
    _attr_translation_key = "vehicle_location"

    def __init__(self, coordinator: ScorpionTrackCoordinator, vehicle_id: int) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, vehicle_id)
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}"

    def _available_vehicle(self) -> ScorpionTrackVehicle | None:
        """Return the vehicle if the tracker is available."""
        if not super().available:
            return None
        return self.get_vehicle()

    @property
    @override
    def available(self) -> bool:
        """Return if the tracker is available."""
        vehicle = self._available_vehicle()
        if vehicle is None:
            return False

        return (
            vehicle.position.latitude is not None
            and vehicle.position.longitude is not None
        )

    @property
    @override
    def latitude(self) -> float | None:
        """Return the latitude."""
        vehicle = self._available_vehicle()
        if vehicle is None:
            return None
        return vehicle.position.latitude

    @property
    @override
    def longitude(self) -> float | None:
        """Return the longitude."""
        vehicle = self._available_vehicle()
        if vehicle is None:
            return None
        return vehicle.position.longitude
