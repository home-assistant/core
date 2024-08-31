"""Support for PoolSense binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PoolSenseConfigEntry
from .entity import PoolSenseEntity

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="pH Status",
        translation_key="ph_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="Chlorine Status",
        translation_key="chlorine_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PoolSenseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        PoolSenseBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
    )


class PoolSenseBinarySensor(PoolSenseEntity, BinarySensorEntity):
    """Representation of PoolSense binary sensors."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data[self.entity_description.key] == "red"
