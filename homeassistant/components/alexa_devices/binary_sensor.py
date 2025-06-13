"""Support for binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from aioamazondevices.api import AmazonDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry
from .entity import AmazonEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AmazonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Alexa Devices binary sensor entity description."""

    is_on_fn: Callable[[AmazonDevice], bool]


BINARY_SENSORS: Final = (
    AmazonBinarySensorEntityDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda _device: _device.online,
    ),
    AmazonBinarySensorEntityDescription(
        key="bluetooth",
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="bluetooth",
        is_on_fn=lambda _device: _device.bluetooth_state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices binary sensors based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        AmazonBinarySensorEntity(coordinator, serial_num, sensor_desc)
        for sensor_desc in BINARY_SENSORS
        for serial_num in coordinator.data
    )


class AmazonBinarySensorEntity(AmazonEntity, BinarySensorEntity):
    """Binary sensor device."""

    entity_description: AmazonBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.device)
