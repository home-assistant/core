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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity


@dataclass
class RoborockBinarySensorDescriptionMixin:
    """A class that describes binary sensor entities."""

    value_fn: Callable[[DeviceProp], bool]


@dataclass
class RoborockBinarySensorDescription(
    BinarySensorEntityDescription, RoborockBinarySensorDescriptionMixin
):
    """A class that describes Roborock binary sensors."""


BINARY_SENSOR_DESCRIPTIONS = [
    RoborockBinarySensorDescription(
        key="dry_status",
        translation_key="mop_drying_status",
        icon="mdi:heat-wave",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.dry_status,
    ),
    RoborockBinarySensorDescription(
        key="water_box_carriage_status",
        translation_key="mop_attached",
        icon="mdi:square-rounded",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.water_box_carriage_status,
    ),
    RoborockBinarySensorDescription(
        key="water_box_status",
        translation_key="water_box_attached",
        icon="mdi:water",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.water_box_status,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock vacuum binary sensors."""
    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RoborockBinarySensorEntity(
            f"{description.key}_{slugify(device_id)}",
            coordinator,
            description,
        )
        for device_id, coordinator in coordinators.items()
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.value_fn(coordinator.roborock_device_info.props) is not None
    )


class RoborockBinarySensorEntity(RoborockCoordinatedEntity, BinarySensorEntity):
    """Representation of a Roborock binary sensor."""

    entity_description: RoborockBinarySensorDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockBinarySensorDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(unique_id, coordinator)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the value reported by the sensor."""
        return bool(
            self.entity_description.value_fn(
                self.coordinator.roborock_device_info.props
            )
        )
