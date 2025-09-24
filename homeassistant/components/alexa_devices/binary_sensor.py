"""Support for binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from aioamazondevices.api import AmazonDevice
from aioamazondevices.const import SENSOR_STATE_OFF

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry
from .entity import AmazonEntity
from .utils import async_update_unique_id

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AmazonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Alexa Devices binary sensor entity description."""

    is_on_fn: Callable[[AmazonDevice, str], bool]
    is_supported: Callable[[AmazonDevice, str], bool] = lambda device, key: True
    is_available_fn: Callable[[AmazonDevice, str], bool] = lambda device, key: True


BINARY_SENSORS: Final = (
    AmazonBinarySensorEntityDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device, _: device.online,
    ),
    AmazonBinarySensorEntityDescription(
        key="detectionState",
        device_class=BinarySensorDeviceClass.MOTION,
        is_on_fn=lambda device, key: bool(
            device.sensors[key].value != SENSOR_STATE_OFF
        ),
        is_supported=lambda device, key: device.sensors.get(key) is not None,
        is_available_fn=lambda device, key: (
            device.online and device.sensors[key].error is False
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices binary sensors based on a config entry."""

    coordinator = entry.runtime_data

    # Replace unique id for "detectionState" binary sensor
    await async_update_unique_id(
        hass,
        coordinator,
        BINARY_SENSOR_DOMAIN,
        "humanPresenceDetectionState",
        "detectionState",
    )

    async_add_entities(
        AmazonBinarySensorEntity(coordinator, serial_num, sensor_desc)
        for sensor_desc in BINARY_SENSORS
        for serial_num in coordinator.data
        if sensor_desc.is_supported(coordinator.data[serial_num], sensor_desc.key)
    )

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                AmazonBinarySensorEntity(coordinator, serial_num, sensor_desc)
                for sensor_desc in BINARY_SENSORS
                for serial_num in new_devices
                if sensor_desc.is_supported(
                    coordinator.data[serial_num], sensor_desc.key
                )
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AmazonBinarySensorEntity(AmazonEntity, BinarySensorEntity):
    """Binary sensor device."""

    entity_description: AmazonBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.is_on_fn(
            self.device, self.entity_description.key
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.entity_description.is_available_fn(
                self.device, self.entity_description.key
            )
            and super().available
        )
