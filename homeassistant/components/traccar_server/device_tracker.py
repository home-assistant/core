"""Support for Traccar server device tracking."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_CATEGORY, ATTR_TRACCAR_ID, ATTR_TRACKER, DOMAIN
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific attributes."""
        return {
            **self.traccar_attributes,
            ATTR_CATEGORY: self.traccar_device["category"],
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
