"""Support for Aqualink temperature sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AqualinkEntity
from .const import DOMAIN as AQUALINK_DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up discovered binary sensors."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkBinarySensor(dev))
    async_add_entities(devs, True)


class HassAqualinkBinarySensor(AqualinkEntity, BinarySensorEntity):
    """Representation of a binary sensor."""

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return self.dev.label

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on or not."""
        return self.dev.is_on

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the class of the binary sensor."""
        if self.name == "Freeze Protection":
            return BinarySensorDeviceClass.COLD
        return None
