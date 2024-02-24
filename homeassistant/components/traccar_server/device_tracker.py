"""Support for Traccar server device tracking."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ADDRESS,
    ATTR_ALTITUDE,
    ATTR_CATEGORY,
    ATTR_GEOFENCE,
    ATTR_MOTION,
    ATTR_SPEED,
    ATTR_STATUS,
    ATTR_TRACCAR_ID,
    ATTR_TRACKER,
    DOMAIN,
)
from .coordinator import TraccarServerCoordinator
from .entity import TraccarServerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker entities."""
    coordinator: TraccarServerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        TraccarServerDeviceTracker(coordinator, entry["device"])
        for entry in coordinator.data.values()
    )


class TraccarServerDeviceTracker(TraccarServerEntity, TrackerEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True
    _attr_name = None

    @property
    def battery_level(self) -> int:
        """Return battery value of the device."""
        return self.traccar_position["attributes"].get("batteryLevel", -1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific attributes."""
        geofence_name = self.traccar_geofence["name"] if self.traccar_geofence else None
        return {
            **self.traccar_attributes,
            ATTR_ADDRESS: self.traccar_position["address"],
            ATTR_ALTITUDE: self.traccar_position["altitude"],
            ATTR_CATEGORY: self.traccar_device["category"],
            ATTR_GEOFENCE: geofence_name,
            ATTR_MOTION: self.traccar_position["attributes"].get("motion", False),
            ATTR_SPEED: self.traccar_position["speed"],
            ATTR_STATUS: self.traccar_device["status"],
            ATTR_TRACCAR_ID: self.traccar_device["id"],
            ATTR_TRACKER: DOMAIN,
        }

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self.traccar_position["latitude"]

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self.traccar_position["longitude"]

    @property
    def location_accuracy(self) -> int:
        """Return the gps accuracy of the device."""
        return self.traccar_position["accuracy"]

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS
