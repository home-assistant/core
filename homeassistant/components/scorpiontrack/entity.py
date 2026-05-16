"""Shared entity helpers for ScorpionTrack."""

from datetime import timedelta

from pyscorpiontrack import ScorpionTrackShare, ScorpionTrackVehicle

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER, STALE_POSITION_THRESHOLD
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

    def position_age(
        self, vehicle: ScorpionTrackVehicle | None = None
    ) -> timedelta | None:
        """Return the age of the latest reported position."""
        if vehicle is None:
            vehicle = self.get_vehicle()
        if vehicle is None:
            return None

        timestamp = vehicle.position.timestamp
        if timestamp is None:
            return None

        age = dt_util.utcnow() - timestamp
        if age.total_seconds() < 0:
            return timedelta(seconds=0)
        return age

    def position_is_stale(self, vehicle: ScorpionTrackVehicle | None = None) -> bool:
        """Return True if the latest reported position is stale."""
        return _is_position_stale(self.position_age(vehicle))


class ScorpionTrackShareEntity(CoordinatorEntity[ScorpionTrackCoordinator]):
    """Base class for ScorpionTrack share entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ScorpionTrackCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.share.id))},
            entry_type=DeviceEntryType.SERVICE,
            name=self.share.title or DEFAULT_NAME,
        )

    @property
    def share(self) -> ScorpionTrackShare:
        """Return the active share data."""
        return self.coordinator.data


def _is_position_stale(age: timedelta | None) -> bool:
    """Return True if a reported position age should be treated as stale."""
    return age is None or age >= STALE_POSITION_THRESHOLD
