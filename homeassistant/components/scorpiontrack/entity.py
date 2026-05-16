"""Shared entity helpers for ScorpionTrack."""

from pyscorpiontrack import ScorpionTrackShare, ScorpionTrackVehicle

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ScorpionTrackCoordinator


class ScorpionTrackEntity(CoordinatorEntity[ScorpionTrackCoordinator]):
    """Base class for ScorpionTrack vehicle entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ScorpionTrackCoordinator, vehicle_id: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        vehicle = self.get_vehicle()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self.share.id}_{vehicle_id}")},
            manufacturer=(vehicle.make or MANUFACTURER) if vehicle else MANUFACTURER,
            model=vehicle.model if vehicle else None,
            name=vehicle.display_name if vehicle else f"Vehicle {vehicle_id}",
        )

    @property
    def share(self) -> ScorpionTrackShare:
        """Return the active share data."""
        return self.coordinator.data

    def get_vehicle(self) -> ScorpionTrackVehicle | None:
        """Return the matching vehicle, if present."""
        for vehicle in self.share.vehicles:
            if vehicle.id == self._vehicle_id:
                return vehicle
        return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.get_vehicle() is not None
