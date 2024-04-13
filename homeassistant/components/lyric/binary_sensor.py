"""Support for Honeywell Lyric binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiolyric import Lyric
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricRoom

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import LyricRoomEntity
from .const import DOMAIN


@dataclass(frozen=True)
class LyricRoomBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[LyricRoom], bool]


@dataclass(frozen=True)
class LyricRoomBinarySensorEntityDescription(
    BinarySensorEntityDescription, LyricRoomBinarySensorEntityDescriptionMixin
):
    """Class describing Honeywell Lyric room binary sensor entities."""


ROOM_SENSORS = [
    LyricRoomBinarySensorEntityDescription(
        key="overall_motion",
        translation_key="overall_motion",
        name="overall motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda room: room.overallMotion,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Honeywell Lyric binary sensor platform based on a config entry."""
    coordinator: DataUpdateCoordinator[Lyric] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        LyricRoomBinarySensor(
            coordinator,
            room_sensor,
            location,
            device,
            room,
        )
        for location in coordinator.data.locations
        for device in location.devices
        for room in coordinator.data.rooms_dict[device.macID].values()
        for room_sensor in ROOM_SENSORS
    )


class LyricRoomBinarySensor(LyricRoomEntity, BinarySensorEntity):
    """Define a Honeywell Lyric room binary sensor."""

    entity_description: LyricRoomBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        description: LyricRoomBinarySensorEntityDescription,
        location: LyricLocation,
        device: LyricDevice,
        room: LyricRoom,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            location,
            device,
            room,
            f"{device.macID}_room_{room.id}_{description.key}",
        )
        self.entity_description = description
        room_name = room.roomName or f"Room {room.id}"
        self._attr_name = f"{room_name} {description.name}"

    @property
    def is_on(self) -> bool:
        """Return the binary state."""
        return self.entity_description.value_fn(self.room)
