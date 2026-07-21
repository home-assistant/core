"""Support for Honeywell Lyric binary sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricAccessory, LyricRoom

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LyricConfigEntry, LyricDataUpdateCoordinator
from .entity import LyricAccessoryEntity


@dataclass(frozen=True, kw_only=True)
class LyricBinarySensorAccessoryEntityDescription(BinarySensorEntityDescription):
    """Class describing Honeywell Lyric room sensor binary sensor entities."""

    value_fn: Callable[[LyricRoom, LyricAccessory], bool]
    suitable_fn: Callable[[LyricRoom, LyricAccessory], bool]


ACCESSORY_BINARY_SENSORS: list[LyricBinarySensorAccessoryEntityDescription] = [
    LyricBinarySensorAccessoryEntityDescription(
        key="room_motion",
        translation_key="room_motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda _, accessory: accessory.detect_motion,
        suitable_fn=lambda _, accessory: accessory.type == "IndoorAirSensor",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LyricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Honeywell Lyric binary sensor platform based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        LyricAccessoryBinarySensor(
            coordinator, binary_sensor, location, device, room, accessory
        )
        for location in coordinator.data.locations
        for device in location.devices
        for room in coordinator.data.rooms_dict.get(device.mac_id, {}).values()
        for accessory in room.accessories
        for binary_sensor in ACCESSORY_BINARY_SENSORS
        if binary_sensor.suitable_fn(room, accessory)
    )


class LyricAccessoryBinarySensor(LyricAccessoryEntity, BinarySensorEntity):
    """Define a Honeywell Lyric room sensor binary sensor."""

    entity_description: LyricBinarySensorAccessoryEntityDescription

    def __init__(
        self,
        coordinator: LyricDataUpdateCoordinator,
        description: LyricBinarySensorAccessoryEntityDescription,
        location: LyricLocation,
        parentDevice: LyricDevice,
        room: LyricRoom,
        accessory: LyricAccessory,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            location,
            parentDevice,
            room,
            accessory,
            f"{parentDevice.mac_id}_room{room.id}_acc{accessory.id}_{description.key}",
        )
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return true if motion is detected."""
        return self.entity_description.value_fn(self.room, self.accessory)
