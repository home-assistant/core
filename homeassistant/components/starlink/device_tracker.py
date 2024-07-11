"""Contains device trackers exposed by the Starlink integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_ALTITUDE, DOMAIN
from .coordinator import StarlinkData
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all binary sensors for this entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StarlinkDeviceTrackerEntity(coordinator, description)
        for description in DEVICE_TRACKERS
    )


@dataclass(frozen=True, kw_only=True)
class StarlinkDeviceTrackerEntityDescription(EntityDescription):
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
    def source_type(self) -> SourceType | str:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

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
