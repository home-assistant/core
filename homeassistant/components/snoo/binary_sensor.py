"""Support for Snoo Binary Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from python_snoo.containers import BabyData, SnooData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SnooConfigEntry
from .entity import SnooBabyDescriptionEntity, SnooDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class SnooBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Snoo Binary Sensor."""

    value_fn: Callable[[SnooData], bool]


@dataclass(frozen=True, kw_only=True)
class SnooBabyBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Snoo Baby Binary Sensor."""

    value_fn: Callable[[BabyData], bool]


BINARY_SENSOR_DESCRIPTIONS: list[SnooBinarySensorEntityDescription] = [
    SnooBinarySensorEntityDescription(
        key="left_clip",
        translation_key="left_clip",
        value_fn=lambda data: data.left_safety_clip,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SnooBinarySensorEntityDescription(
        key="right_clip",
        translation_key="right_clip",
        value_fn=lambda data: data.right_safety_clip,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


BABY_BINARY_SENSOR_DESCRIPTIONS: list[SnooBabyBinarySensorEntityDescription] = [
    SnooBabyBinarySensorEntityDescription(
        key="disabled_limiter",
        translation_key="disabled_limiter",
        icon="mdi:car-speed-limiter",
        value_fn=lambda data: data.disabledLimiter,
    ),
    SnooBabyBinarySensorEntityDescription(
        key="car_ride_mode",
        translation_key="car_ride_mode",
        icon="mdi:car-seat",
        value_fn=lambda data: data.settings.carRideMode,
    ),
    SnooBabyBinarySensorEntityDescription(
        key="motion_limiter",
        translation_key="motion_limiter",
        icon="mdi:motion-pause",
        value_fn=lambda data: data.settings.motionLimiter,
    ),
    SnooBabyBinarySensorEntityDescription(
        key="weaning",
        translation_key="weaning",
        icon="mdi:baby-bottle-outline",
        value_fn=lambda data: data.settings.weaning,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Snoo device and baby binary sensors."""
    coordinators = entry.runtime_data

    binary_sensors: list[BinarySensorEntity] = []
    for coordinator in coordinators.values():
        binary_sensors.extend(
            SnooBinarySensor(coordinator, description)
            for description in BINARY_SENSOR_DESCRIPTIONS
        )

        binary_sensors.extend(
            SnooBabyBinarySensor(baby_coordinator, description)
            for baby_coordinator in coordinator.baby_coordinators.values()
            for description in BABY_BINARY_SENSOR_DESCRIPTIONS
        )

    async_add_entities(binary_sensors)


class SnooBinarySensor(SnooDescriptionEntity, BinarySensorEntity):
    """A Binary sensor using Snoo coordinator."""

    entity_description: SnooBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)


class SnooBabyBinarySensor(SnooBabyDescriptionEntity, BinarySensorEntity):
    """A Binary sensor using Snoo baby coordinator."""

    entity_description: SnooBabyBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
