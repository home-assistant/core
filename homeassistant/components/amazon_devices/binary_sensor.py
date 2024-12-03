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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AmazonDevicesCoordinator


@dataclass(frozen=True, kw_only=True)
class AmazonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Amazon Devices binary sensor entity description."""

    is_on_fn: Callable[
        [AmazonDevice],
        bool,
    ]


BINARY_SENSORS: Final = (
    AmazonBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        name="Online",
        is_on_fn=lambda _device: bool(_device.online),
    ),
    AmazonBinarySensorEntityDescription(
        key="bluetooth_state",
        translation_key="bluetooth_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        name="Bluetooth state",
        is_on_fn=lambda _device: bool(_device.bluetooth_state),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit binary sensors."""

    coordinator: AmazonDevicesCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[AmazonBinarySensorEntity] = []
    for serial_num in coordinator.data:
        entities.extend(
            AmazonBinarySensorEntity(coordinator, serial_num, sensor_desc)
            for sensor_desc in BINARY_SENSORS
        )

    async_add_entities(entities)


class AmazonBinarySensorEntity(
    CoordinatorEntity[AmazonDevicesCoordinator], BinarySensorEntity
):
    """Binary sensor device."""

    _attr_has_entity_name = True
    entity_description: AmazonBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
        description: AmazonBinarySensorEntityDescription,
    ) -> None:
        """Init sensor entity."""
        self._api = coordinator.api
        self._device: AmazonDevice = coordinator.data[serial_num]

        super().__init__(coordinator)

        self._attr_unique_id = f"{self._device.serial_number}-{description.key}"
        self._attr_device_info = coordinator.device_info(self._device)

        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Presence detected."""
        return self.entity_description.is_on_fn(self._device)
