"""Shared entity helpers for ScorpionTrack."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pyscorpiontrack import ScorpionTrackShare, ScorpionTrackVehicle

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER, STALE_POSITION_THRESHOLD
from .coordinator import ScorpionTrackCoordinator


class ScorpionTrackEntity(CoordinatorEntity[ScorpionTrackCoordinator]):
    """Base class for ScorpionTrack vehicle entities."""

    def __init__(self, coordinator: ScorpionTrackCoordinator, vehicle_id: int) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._device_identifier = (DOMAIN, f"{self.share.id}_{vehicle_id}")
        self._cached_display_name = f"Vehicle {vehicle_id}"
        self._cached_registration: str | None = None
        self._cached_manufacturer = MANUFACTURER
        self._cached_model: str | None = None

        if vehicle := self.get_vehicle():
            self._cache_vehicle_metadata(vehicle)

    def _cache_vehicle_metadata(self, vehicle: ScorpionTrackVehicle) -> None:
        """Cache the latest immutable vehicle metadata."""
        self._cached_display_name = vehicle.display_name
        self._cached_registration = vehicle.registration
        self._cached_manufacturer = vehicle.make or MANUFACTURER
        self._cached_model = vehicle.model

    @property
    def share(self) -> ScorpionTrackShare:
        """Return the active share data."""
        return self.coordinator.data

    def get_vehicle(self) -> ScorpionTrackVehicle | None:
        """Return the matching vehicle, if present."""
        for vehicle in self.share.vehicles:
            if vehicle.id == self._vehicle_id:
                self._cache_vehicle_metadata(vehicle)
                return vehicle
        return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.get_vehicle() is not None

    def position_age(self) -> timedelta | None:
        """Return the age of the latest reported position."""
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

    def position_is_stale(self) -> bool:
        """Return True if the latest reported position is stale."""
        age = self.position_age()
        return age is None or age >= STALE_POSITION_THRESHOLD

    def common_location_attributes(
        self,
        *,
        include_coordinates: bool = False,
    ) -> dict[str, Any]:
        """Return shared location-related attributes."""
        vehicle = self.get_vehicle()
        position = vehicle.position if vehicle else None
        age = self.position_age()
        age_seconds = max(0, int(age.total_seconds())) if age is not None else None

        attributes = {
            "registration": vehicle.registration
            if vehicle
            else self._cached_registration,
            "make": vehicle.make if vehicle else self._cached_manufacturer,
            "model": vehicle.model if vehicle else self._cached_model,
            "status": vehicle.status if vehicle else None,
            "bearing": position.bearing if position else None,
            "heading_cardinal": _bearing_to_cardinal(
                position.bearing if position else None
            ),
            "address": position.address if position else None,
            "ignition": position.ignition if position else None,
            "last_reported": position.timestamp.isoformat()
            if position and position.timestamp
            else None,
            "last_reported_age_seconds": age_seconds,
            "stale": self.position_is_stale(),
            "stale_after_hours": int(STALE_POSITION_THRESHOLD.total_seconds() // 3600),
            "removed_from_share": vehicle is None,
            "share_title": self.share.title,
            "shared_by": self.share.owner_name,
            "share_expires": self.share.expires_at.isoformat()
            if self.share.expires_at
            else None,
        }
        if include_coordinates:
            attributes["latitude"] = position.latitude if position else None
            attributes["longitude"] = position.longitude if position else None
        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device metadata for the vehicle."""
        return DeviceInfo(
            identifiers={self._device_identifier},
            manufacturer=self._cached_manufacturer,
            model=self._cached_model,
            name=self._cached_display_name,
        )


def _bearing_to_cardinal(bearing: float | None) -> str | None:
    """Convert a numeric bearing into a cardinal heading."""
    if bearing is None:
        return None

    directions = (
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    )
    index = int((bearing % 360) / 22.5 + 0.5) % len(directions)
    return directions[index]
