"""Support for Honeywell Lyric binary sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import cast

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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import LyricRoomEntity
from .const import DOMAIN


@dataclass
class LyricRoomBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Honeywell Lyric sensor entities."""

    is_on: Callable[[LyricRoom], StateType | datetime] = round


class LyricRoomBinarySensor(LyricRoomEntity, BinarySensorEntity):
    """Define a Honeywell Lyric binary sensor."""

    coordinator: DataUpdateCoordinator[Lyric]
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
            description.key,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        room: LyricRoom = self.room
        try:
            return cast(bool, self.entity_description.is_on(room))
        except TypeError:
            return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Honeywell Lyric binary sensor platform based on a config entry."""

    coordinator: DataUpdateCoordinator[Lyric] = hass.data[DOMAIN][entry.entry_id]
    entities: list[Entity] = []

    for location in coordinator.data.locations:
        for device in location.devices:
            if device.macID in coordinator.data.rooms_dict:
                room: LyricRoom
                for room in coordinator.data.rooms_dict[device.macID].values():
                    if hasattr(room, "overallMotion"):
                        entities.append(
                            LyricRoomBinarySensor(
                                coordinator,
                                LyricRoomBinarySensorEntityDescription(
                                    key=f"{device.macID}_room{room.id}_motion",
                                    name=f"{room.roomName} Overall Motion",
                                    device_class=BinarySensorDeviceClass.MOTION,
                                    is_on=lambda room: room.overallMotion,
                                ),
                                location,
                                device,
                                room,
                            )
                        )

    async_add_entities(entities, True)
