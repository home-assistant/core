"""Support for Roborock sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from roborock.roborock_typing import DeviceProp

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RoborockConfigEntry
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntityV1


@dataclass(frozen=True, kw_only=True)
class RoborockBinarySensorDescription(BinarySensorEntityDescription):
    """A class that describes Roborock binary sensors."""

    value_fn: Callable[[DeviceProp], bool | int | None]


BINARY_SENSOR_DESCRIPTIONS = [
    RoborockBinarySensorDescription(
        key="dry_status",
        translation_key="mop_drying_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.dry_status,
    ),
    RoborockBinarySensorDescription(
        key="water_box_carriage_status",
        translation_key="mop_attached",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.water_box_carriage_status,
    ),
    RoborockBinarySensorDescription(
        key="water_box_status",
        translation_key="water_box_attached",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.water_box_status,
    ),
    RoborockBinarySensorDescription(
        key="water_shortage",
        translation_key="water_shortage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.water_shortage_status,
    ),
    RoborockBinarySensorDescription(
        key="in_cleaning",
        translation_key="in_cleaning",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.in_cleaning,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock vacuum binary sensors."""
    async_add_entities(
        RoborockBinarySensorEntity(
            coordinator,
            description,
        )
        for coordinator in config_entry.runtime_data.v1
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.value_fn(coordinator.roborock_device_info.props) is not None
    )


class RoborockBinarySensorEntity(RoborockCoordinatedEntityV1, BinarySensorEntity):
    """Representation of a Roborock binary sensor."""

    entity_description: RoborockBinarySensorDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockBinarySensorDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            f"{description.key}_{coordinator.duid_slug}",
            coordinator,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the value reported by the sensor."""
        return bool(
            self.entity_description.value_fn(
                self.coordinator.roborock_device_info.props
            )
        )
