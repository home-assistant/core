"""Binary Sensor platform for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import MotionSensor, SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, SensiboMotionBaseEntity


@dataclass
class MotionBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[MotionSensor], bool | None]


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[dict[str, Any]], bool | None]


@dataclass
class SensiboMotionBinarySensorEntityDescription(
    BinarySensorEntityDescription, MotionBaseEntityDescriptionMixin
):
    """Describes Sensibo Motion sensor entity."""


@dataclass
class SensiboDeviceBinarySensorEntityDescription(
    BinarySensorEntityDescription, DeviceBaseEntityDescriptionMixin
):
    """Describes Sensibo Motion sensor entity."""


MOTION_SENSOR_TYPES: tuple[SensiboMotionBinarySensorEntityDescription, ...] = (
    SensiboMotionBinarySensorEntityDescription(
        key="alive",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Alive",
        icon="mdi:wifi",
        value_fn=lambda data: data.alive,
    ),
    SensiboMotionBinarySensorEntityDescription(
        key="is_main_sensor",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Is Main Sensor",
        icon="mdi:connection",
        value_fn=lambda data: data.is_main_sensor,
    ),
    SensiboMotionBinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        name="Motion",
        icon="mdi:motion-sensor",
        value_fn=lambda data: data.motion,
    ),
)

DEVICE_SENSOR_TYPES: tuple[SensiboDeviceBinarySensorEntityDescription, ...] = (
    SensiboDeviceBinarySensorEntityDescription(
        key="room_occupied",
        device_class=BinarySensorDeviceClass.MOTION,
        name="Room Occupied",
        icon="mdi:motion-sensor",
        value_fn=lambda data: data["room_occupied"],
    ),
    SensiboDeviceBinarySensorEntityDescription(
        key="update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Update Available",
        icon="mdi:rocket-launch",
        value_fn=lambda data: data["update_available"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo binary sensor platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensiboMotionSensor | SensiboDeviceSensor] = []
    LOGGER.debug("parsed data: %s", coordinator.data.parsed)
    entities.extend(
        SensiboMotionSensor(coordinator, device_id, sensor_id, sensor_data, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for sensor_id, sensor_data in device_data["motion_sensors"].items()
        for description in MOTION_SENSOR_TYPES
        if device_data["motion_sensors"]
    )
    LOGGER.debug("start device %s", entities)
    entities.extend(
        SensiboDeviceSensor(coordinator, device_id, description)
        for description in DEVICE_SENSOR_TYPES
        for device_id, device_data in coordinator.data.parsed.items()
        if device_data[description.key] is not None
    )
    LOGGER.debug("list: %s", entities)

    async_add_entities(entities)


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
            entity_description.name,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{sensor_id}-{entity_description.key}"
        self._attr_name = (
            f"{self.device_data['name']} Motion Sensor {entity_description.name}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
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
        self._attr_name = f"{self.device_data['name']} {entity_description.name}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.device_data)
