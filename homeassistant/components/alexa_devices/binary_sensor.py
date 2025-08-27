"""Support for binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from aioamazondevices.api import AmazonDevice

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.helpers.entity_registry as er

from .const import _LOGGER, DOMAIN
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
)

DEPRECATED_BINARY_SENSORS: Final = (
    AmazonBinarySensorEntityDescription(
        key="bluetooth",
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="bluetooth",
        is_on_fn=lambda device, key: False,
    ),
    AmazonBinarySensorEntityDescription(
        key="babyCryDetectionState",
        translation_key="baby_cry_detection",
        is_on_fn=lambda device, key: False,
    ),
    AmazonBinarySensorEntityDescription(
        key="beepingApplianceDetectionState",
        translation_key="beeping_appliance_detection",
        is_on_fn=lambda device, key: False,
    ),
    AmazonBinarySensorEntityDescription(
        key="coughDetectionState",
        translation_key="cough_detection",
        is_on_fn=lambda device, key: False,
    ),
    AmazonBinarySensorEntityDescription(
        key="dogBarkDetectionState",
        translation_key="dog_bark_detection",
        is_on_fn=lambda device, key: False,
    ),
    AmazonBinarySensorEntityDescription(
        key="humanPresenceDetectionState",
        device_class=BinarySensorDeviceClass.MOTION,
        is_on_fn=lambda device, key: False,
    ),
    AmazonBinarySensorEntityDescription(
        key="waterSoundsDetectionState",
        translation_key="water_sounds_detection",
        is_on_fn=lambda device, key: False,
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
        if sensor_desc.is_supported(coordinator.data[serial_num], sensor_desc.key)
    )

    # Clean up deprecated sensors
    entity_registry = er.async_get(hass)
    for sensor_desc in DEPRECATED_BINARY_SENSORS:
        for serial_num in coordinator.data:
            unique_id = f"{serial_num}-{sensor_desc.key}"
            if entity_id := entity_registry.async_get_entity_id(
                BINARY_SENSOR_DOMAIN, DOMAIN, unique_id
            ):
                _LOGGER.debug("Removing deprecated entity %s", entity_id)
                entity_registry.async_remove(entity_id)


class AmazonBinarySensorEntity(AmazonEntity, BinarySensorEntity):
    """Binary sensor device."""

    entity_description: AmazonBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.is_on_fn(
            self.device, self.entity_description.key
        )
