"""Support for the linknlink binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LinknLinkEntity

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="pir_detected",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the linknlink binary sensor."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    binarysensors = [
        LinknLinkBinarySensor(device, description)
        for description in BINARY_SENSOR_TYPES
    ]
    async_add_entities(binarysensors)


class LinknLinkBinarySensor(LinknLinkEntity, BinarySensorEntity):
    """Representation of a linknlink binary sensor."""

    _attr_has_entity_name = True

    def __init__(self, device, description: BinarySensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self.entity_description = description

        self._attr_native_value = self._coordinator.data[description.key]
        self._attr_unique_id = f"{device.unique_id}-{description.key}"

    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_native_value = data[self.entity_description.key]
