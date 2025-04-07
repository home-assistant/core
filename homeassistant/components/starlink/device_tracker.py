"""Contains device trackers exposed by the Starlink integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.device_tracker import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_ALTITUDE
from .coordinator import StarlinkConfigEntry, StarlinkData
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: StarlinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all binary sensors for this entry."""
    async_add_entities(
        StarlinkDeviceTrackerEntity(config_entry.runtime_data, description)
        for description in DEVICE_TRACKERS
    )


@dataclass(frozen=True, kw_only=True)
class StarlinkDeviceTrackerEntityDescription(TrackerEntityDescription):
    """Describes a Starlink button entity."""

    latitude_fn: Callable[[StarlinkData], float]
    longitude_fn: Callable[[StarlinkData], float]
    altitude_fn: Callable[[StarlinkData], float]


DEVICE_TRACKERS = [
    StarlinkDeviceTrackerEntityDescription(
        key="device_location",
        translation_key="device_location",
        entity_registry_enabled_default=False,
        latitude_fn=lambda data: data.location["latitude"],
        longitude_fn=lambda data: data.location["longitude"],
        altitude_fn=lambda data: data.location["altitude"],
    ),
]


class StarlinkDeviceTrackerEntity(StarlinkEntity, TrackerEntity):
    """A TrackerEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkDeviceTrackerEntityDescription

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.entity_description.latitude_fn(self.coordinator.data)

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.entity_description.longitude_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific attributes."""
        return {
            ATTR_ALTITUDE: self.entity_description.altitude_fn(self.coordinator.data)
        }
