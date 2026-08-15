"""Support for Honeywell Lyric binary sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LyricConfigEntry, LyricDataUpdateCoordinator
from .entity import LyricDeviceEntity


@dataclass(frozen=True, kw_only=True)
class LyricBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Honeywell Lyric binary sensor entities."""

    value_fn: Callable[[LyricDevice], bool]
    suitable_fn: Callable[[LyricDevice], bool]


DEVICE_BINARY_SENSORS: list[LyricBinarySensorEntityDescription] = [
    LyricBinarySensorEntityDescription(
        key="device_pairing_enabled",
        translation_key="device_pairing_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.settings.device_pairing_enabled,
        suitable_fn=lambda device: True,
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
        LyricBinarySensor(
            coordinator,
            device_binary_sensor,
            location,
            device,
        )
        for location in coordinator.data.locations
        for device in location.devices
        for device_binary_sensor in DEVICE_BINARY_SENSORS
        if device_binary_sensor.suitable_fn(device)
    )


class LyricBinarySensor(LyricDeviceEntity, BinarySensorEntity):
    """Define a Honeywell Lyric binary sensor."""

    entity_description: LyricBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: LyricDataUpdateCoordinator,
        description: LyricBinarySensorEntityDescription,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            location,
            device,
            f"{device.mac_id}_{description.key}",
        )
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the condition is met."""
        return self.entity_description.value_fn(self.device)
