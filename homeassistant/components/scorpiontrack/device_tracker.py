"""Device tracker platform for ScorpionTrack."""

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
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
    async_add_entities(
        ScorpionTrackTrackerEntity(coordinator, vehicle.id)
        for vehicle in coordinator.data.vehicles
    )


class ScorpionTrackTrackerEntity(ScorpionTrackEntity, TrackerEntity):
    """Represent the latest shared GPS location for a vehicle."""

    _attr_has_entity_name = True
    _attr_location_accuracy = 0.0
    _attr_name = None
    _attr_source_type = SourceType.GPS
    _attr_translation_key = "vehicle_location"

    def __init__(self, coordinator: ScorpionTrackCoordinator, vehicle_id: int) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, vehicle_id)
        self._attr_unique_id = f"{coordinator.data.id}_{vehicle_id}"

    @property
    def available(self) -> bool:
        """Return if the tracker is available."""
        vehicle = self.get_vehicle()
        if not self.coordinator.last_update_success or vehicle is None:
            return False

        return (
            vehicle.position.latitude is not None
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
