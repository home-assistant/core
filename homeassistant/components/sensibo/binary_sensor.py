"""Binary Sensor platform for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pysensibo.model import MotionSensor, SensiboDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, SensiboMotionBaseEntity

PARALLEL_UPDATES = 0


@dataclass
class MotionBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[MotionSensor], bool | None]


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[SensiboDevice], bool | None]


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


FILTER_CLEAN_REQUIRED_DESCRIPTION = SensiboDeviceBinarySensorEntityDescription(
    key="filter_clean",
    device_class=BinarySensorDeviceClass.PROBLEM,
    name="Filter Clean Required",
    value_fn=lambda data: data.filter_clean,
)

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
        name="Main Sensor",
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

MOTION_DEVICE_SENSOR_TYPES: tuple[SensiboDeviceBinarySensorEntityDescription, ...] = (
    SensiboDeviceBinarySensorEntityDescription(
        key="room_occupied",
        device_class=BinarySensorDeviceClass.MOTION,
        name="Room Occupied",
        icon="mdi:motion-sensor",
        value_fn=lambda data: data.room_occupied,
    ),
)

DEVICE_SENSOR_TYPES: tuple[SensiboDeviceBinarySensorEntityDescription, ...] = (
    FILTER_CLEAN_REQUIRED_DESCRIPTION,
)

PURE_SENSOR_TYPES: tuple[SensiboDeviceBinarySensorEntityDescription, ...] = (
    SensiboDeviceBinarySensorEntityDescription(
        key="pure_ac_integration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        name="Pure Boost linked with AC",
        icon="mdi:connection",
        value_fn=lambda data: data.pure_ac_integration,
    ),
    SensiboDeviceBinarySensorEntityDescription(
        key="pure_geo_integration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        name="Pure Boost linked with Presence",
        icon="mdi:connection",
        value_fn=lambda data: data.pure_geo_integration,
    ),
    SensiboDeviceBinarySensorEntityDescription(
        key="pure_measure_integration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        name="Pure Boost linked with Indoor Air Quality",
        icon="mdi:connection",
        value_fn=lambda data: data.pure_measure_integration,
    ),
    SensiboDeviceBinarySensorEntityDescription(
        key="pure_prime_integration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        name="Pure Boost linked with Outdoor Air Quality",
        icon="mdi:connection",
        value_fn=lambda data: data.pure_prime_integration,
    ),
    FILTER_CLEAN_REQUIRED_DESCRIPTION,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo binary sensor platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensiboMotionSensor | SensiboDeviceSensor] = []

    for device_id, device_data in coordinator.data.parsed.items():
        if device_data.motion_sensors:
            entities.extend(
                SensiboMotionSensor(
                    coordinator, device_id, sensor_id, sensor_data, description
                )
                for sensor_id, sensor_data in device_data.motion_sensors.items()
                for description in MOTION_SENSOR_TYPES
            )
    entities.extend(
        SensiboDeviceSensor(coordinator, device_id, description)
        for description in MOTION_DEVICE_SENSOR_TYPES
        for device_id, device_data in coordinator.data.parsed.items()
        if device_data.motion_sensors
    )
    entities.extend(
        SensiboDeviceSensor(coordinator, device_id, description)
        for description in PURE_SENSOR_TYPES
        for device_id, device_data in coordinator.data.parsed.items()
        if device_data.model == "pure"
    )
    entities.extend(
        SensiboDeviceSensor(coordinator, device_id, description)
        for description in DEVICE_SENSOR_TYPES
        for device_id, device_data in coordinator.data.parsed.items()
        if device_data.model != "pure"
    )

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
            f"{self.device_data.name} Motion Sensor {entity_description.name}"
        )

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
        self._attr_name = f"{self.device_data.name} {entity_description.name}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.device_data)
