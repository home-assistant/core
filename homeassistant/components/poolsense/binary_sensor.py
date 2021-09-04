"""Support for PoolSense binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_EMAIL

from . import PoolSenseEntity
from .const import DOMAIN

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="pH Status",
        unit_of_measurement=None,
        icon=None,
        name="pH Status",
        device_class=DEVICE_CLASS_PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="Chlorine Status",
        unit_of_measurement=None,
        icon=None,
        name="Chlorine Status",
        device_class=DEVICE_CLASS_PROBLEM,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        PoolSenseBinarySensor(coordinator, config_entry.data[CONF_EMAIL], description)
        for description in BINARY_SENSOR_TYPES
    ]

    async_add_entities(entities, False)


class PoolSenseBinarySensor(PoolSenseEntity, BinarySensorEntity):
    """Representation of PoolSense binary sensors."""

    def __init__(self, coordinator, email, description: BinarySensorEntityDescription):
        """Initialize PoolSense binary_sensor."""
        super().__init__(coordinator, email, description)
        self._attr_name = f"PoolSense {description.name}"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.coordinator.data[self.entity_description.key] == "red"
