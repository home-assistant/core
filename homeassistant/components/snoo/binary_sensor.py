"""Support for Snoo Binary Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from python_snoo.containers import SnooData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SnooConfigEntry
from .entity import SnooDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class SnooBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Snoo Binary Sensor."""

    value_fn: Callable[[SnooData], bool]


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
        value_fn=lambda data: data.left_safety_clip,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Snoo device."""
    coordinators = entry.runtime_data
    async_add_entities(
        SnooBinarySensor(coordinator, description)
        for coordinator in coordinators.values()
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class SnooBinarySensor(SnooDescriptionEntity, BinarySensorEntity):
    """A Binary sensor using Snoo coordinator."""

    entity_description: SnooBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
