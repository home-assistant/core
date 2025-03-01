"""Binary Sensor platform for Sensibo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from pysensibo.model import MotionSensor, SensiboDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SensiboConfigEntry
from .const import LOGGER
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, SensiboMotionBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SensiboMotionBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Sensibo Motion binary sensor entity."""

    value_fn: Callable[[MotionSensor], bool | None]


@dataclass(frozen=True, kw_only=True)
class SensiboDeviceBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Sensibo Motion binary sensor entity."""

    value_fn: Callable[[SensiboDevice], bool | None]


FILTER_CLEAN_REQUIRED_DESCRIPTION = SensiboDeviceBinarySensorEntityDescription(
    key="filter_clean",
    translation_key="filter_clean",
    device_class=BinarySensorDeviceClass.PROBLEM,
    value_fn=lambda data: data.filter_clean,
)

MOTION_SENSOR_TYPES: tuple[SensiboMotionBinarySensorEntityDescription, ...] = (
    SensiboMotionBinarySensorEntityDescription(
        key="alive",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.alive,
    ),
    SensiboMotionBinarySensorEntityDescription(
        key="is_main_sensor",
        translation_key="is_main_sensor",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.is_main_sensor,
    ),
    SensiboMotionBinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda data: data.motion,
    ),
)

MOTION_DEVICE_SENSOR_TYPES: tuple[SensiboDeviceBinarySensorEntityDescription, ...] = (
    SensiboDeviceBinarySensorEntityDescription(
        key="room_occupied",
        translation_key="room_occupied",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda data: data.room_occupied,
    ),
)

DEVICE_SENSOR_TYPES: tuple[SensiboDeviceBinarySensorEntityDescription, ...] = (
    FILTER_CLEAN_REQUIRED_DESCRIPTION,
)

PURE_SENSOR_TYPES: tuple[SensiboDeviceBinarySensorEntityDescription, ...] = (
    SensiboDeviceBinarySensorEntityDescription(
        key="pure_ac_integration",
        translation_key="pure_ac_integration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.pure_ac_integration,
    ),
    SensiboDeviceBinarySensorEntityDescription(
        key="pure_geo_integration",
        translation_key="pure_geo_integration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.pure_geo_integration,
    ),
    SensiboDeviceBinarySensorEntityDescription(
        key="pure_measure_integration",
        translation_key="pure_measure_integration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.pure_measure_integration,
    ),
    SensiboDeviceBinarySensorEntityDescription(
        key="pure_prime_integration",
        translation_key="pure_prime_integration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: data.pure_prime_integration,
    ),
    FILTER_CLEAN_REQUIRED_DESCRIPTION,
)

DESCRIPTION_BY_MODELS = {"pure": PURE_SENSOR_TYPES}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiboConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sensibo binary sensor platform."""

    coordinator = entry.runtime_data

    added_devices: set[str] = set()

    def _add_remove_devices() -> None:
        """Handle additions of devices and sensors."""
        entities: list[SensiboMotionSensor | SensiboDeviceSensor] = []
        nonlocal added_devices
        new_devices, remove_devices, new_added_devices = coordinator.get_devices(
            added_devices
        )
        added_devices = new_added_devices

        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug(
                "New devices: %s, Removed devices: %s, Existing devices: %s",
                new_devices,
                remove_devices,
                added_devices,
            )

        if new_devices:
            entities.extend(
                SensiboMotionSensor(
                    coordinator, device_id, sensor_id, sensor_data, description
                )
                for device_id, device_data in coordinator.data.parsed.items()
                if device_data.motion_sensors
                for sensor_id, sensor_data in device_data.motion_sensors.items()
                if sensor_id in new_devices
                for description in MOTION_SENSOR_TYPES
            )

            entities.extend(
                SensiboDeviceSensor(coordinator, device_id, description)
                for device_id, device_data in coordinator.data.parsed.items()
                if device_data.motion_sensors and device_id in new_devices
                for description in MOTION_DEVICE_SENSOR_TYPES
            )
            entities.extend(
                SensiboDeviceSensor(coordinator, device_id, description)
                for device_id, device_data in coordinator.data.parsed.items()
                if device_id in new_devices
                for description in DESCRIPTION_BY_MODELS.get(
                    device_data.model, DEVICE_SENSOR_TYPES
                )
            )
            async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_add_remove_devices))
    _add_remove_devices()


class SensiboMotionSensor(SensiboMotionBaseEntity, BinarySensorEntity):
    """Representation of a Sensibo Motion Binary Sensor."""

    entity_description: SensiboMotionBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        sensor_id: str,
        sensor_data: MotionSensor,
        entity_description: SensiboMotionBinarySensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Motion Binary Sensor."""
        super().__init__(
            coordinator,
            device_id,
            sensor_id,
            sensor_data,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{sensor_id}-{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if TYPE_CHECKING:
            assert self.sensor_data
        return self.entity_description.value_fn(self.sensor_data)


class SensiboDeviceSensor(SensiboDeviceBaseEntity, BinarySensorEntity):
    """Representation of a Sensibo Device Binary Sensor."""

    entity_description: SensiboDeviceBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboDeviceBinarySensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Device Binary Sensor."""
        super().__init__(
            coordinator,
            device_id,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.device_data)
