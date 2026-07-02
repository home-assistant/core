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
            manufacturer=vehicle.make or MANUFACTURER,
            model=vehicle.model,
            name=vehicle.display_name,
        )

    @property
    def share(self) -> ScorpionTrackShare:
        """Return the active share data."""
        return self.coordinator.data

    def get_vehicle(self) -> ScorpionTrackVehicle:
        """Return the matching vehicle."""
        return self.coordinator.vehicles_by_id[self._vehicle_id]

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._vehicle_id in self.coordinator.vehicles_by_id
