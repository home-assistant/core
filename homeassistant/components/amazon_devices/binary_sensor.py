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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .entity import AmazonEntity


@dataclass(frozen=True, kw_only=True)
class AmazonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Amazon Devices binary sensor entity description."""

    is_on_fn: Callable[[AmazonDevice], bool]


BINARY_SENSORS: Final = (
    AmazonBinarySensorEntityDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda _device: _device.online,
    ),
    AmazonBinarySensorEntityDescription(
        key="bluetooth",
        translation_key="bluetooth",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda _device: _device.bluetooth_state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amazon Devices binary sensors based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        AmazonBinarySensorEntity(coordinator, serial_num, sensor_desc)
        for sensor_desc in BINARY_SENSORS
        for serial_num in coordinator.data
    )


class AmazonBinarySensorEntity(AmazonEntity, BinarySensorEntity):
    """Binary sensor device."""

    entity_description: AmazonBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
        description: AmazonBinarySensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, serial_num)
        self.entity_description = description
        self._attr_unique_id = f"{serial_num}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.device)
