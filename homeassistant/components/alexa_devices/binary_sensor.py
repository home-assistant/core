"""Support for binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from aioamazondevices.api import AmazonDevice
from aioamazondevices.const import SENSOR_STATE_OFF

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

    is_on_fn: Callable[[AmazonDevice, str], bool]
    is_supported: Callable[[AmazonDevice, str], bool] = lambda device, key: True


BINARY_SENSORS: Final = (
    AmazonBinarySensorEntityDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda device, _: device.online,
    ),
    AmazonBinarySensorEntityDescription(
        key="bluetooth",
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="bluetooth",
        is_on_fn=lambda device, _: device.bluetooth_state,
    ),
    AmazonBinarySensorEntityDescription(
        key="babyCryDetectionState",
        translation_key="baby_cry_detection",
        is_on_fn=lambda device, key: (device.sensors[key].value != SENSOR_STATE_OFF),
        is_supported=lambda device, key: device.sensors.get(key) is not None,
    ),
    AmazonBinarySensorEntityDescription(
        key="beepingApplianceDetectionState",
        translation_key="beeping_appliance_detection",
        is_on_fn=lambda device, key: (device.sensors[key].value != SENSOR_STATE_OFF),
        is_supported=lambda device, key: device.sensors.get(key) is not None,
    ),
    AmazonBinarySensorEntityDescription(
        key="coughDetectionState",
        translation_key="cough_detection",
        is_on_fn=lambda device, key: (device.sensors[key].value != SENSOR_STATE_OFF),
        is_supported=lambda device, key: device.sensors.get(key) is not None,
    ),
    AmazonBinarySensorEntityDescription(
        key="dogBarkDetectionState",
        translation_key="dog_bark_detection",
        is_on_fn=lambda device, key: (device.sensors[key].value != SENSOR_STATE_OFF),
        is_supported=lambda device, key: device.sensors.get(key) is not None,
    ),
    AmazonBinarySensorEntityDescription(
        key="humanPresenceDetectionState",
        device_class=BinarySensorDeviceClass.MOTION,
        is_on_fn=lambda device, key: (device.sensors[key].value != SENSOR_STATE_OFF),
        is_supported=lambda device, key: device.sensors.get(key) is not None,
    ),
    AmazonBinarySensorEntityDescription(
        key="waterSoundsDetectionState",
        translation_key="water_sounds_detection",
        is_on_fn=lambda device, key: (device.sensors[key].value != SENSOR_STATE_OFF),
        is_supported=lambda device, key: device.sensors.get(key) is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices binary sensors based on a config entry."""

    coordinator = entry.runtime_data

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
