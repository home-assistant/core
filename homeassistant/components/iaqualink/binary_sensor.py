"""Support for Aqualink temperature sensors."""

from __future__ import annotations

from iaqualink.device import AqualinkBinarySensor

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN as AQUALINK_DOMAIN
from .entity import AqualinkEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up discovered binary sensors."""
    async_add_entities(
        (
            HassAqualinkBinarySensor(dev)
            for dev in hass.data[AQUALINK_DOMAIN][BINARY_SENSOR_DOMAIN]
        ),
        True,
    )


class HassAqualinkBinarySensor(AqualinkEntity, BinarySensorEntity):
    """Representation of a binary sensor."""

    def __init__(self, dev: AqualinkBinarySensor) -> None:
        """Initialize AquaLink binary sensor."""
        super().__init__(dev)
        self._attr_name = dev.label
        if dev.label == "Freeze Protection":
            self._attr_device_class = BinarySensorDeviceClass.COLD

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on or not."""
        return self.dev.is_on
