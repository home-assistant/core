"""Support for Flipr binary sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .entity import FliprEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

BINARY_SENSORS_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="ph_status",
        translation_key="ph_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="chlorine_status",
        translation_key="chlorine_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup of flipr binary sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        FliprBinarySensor(coordinator, description)
        for description in BINARY_SENSORS_TYPES
    )


class FliprBinarySensor(FliprEntity, BinarySensorEntity):
    """Representation of Flipr binary sensors."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on in case of a Problem is detected."""
        return self.coordinator.data[self.entity_description.key] in (
            "TooLow",
            "TooHigh",
        )
