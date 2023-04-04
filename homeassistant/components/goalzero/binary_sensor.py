"""Support for Goal Zero Yeti Sensors."""
from __future__ import annotations

from typing import cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GoalZeroEntity

PARALLEL_UPDATES = 0

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="backlight",
        name="Backlight",
        icon="mdi:clock-digital",
    ),
    BinarySensorEntityDescription(
        key="app_online",
        name="App online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="isCharging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key="inputDetected",
        name="Input detected",
        device_class=BinarySensorDeviceClass.POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Goal Zero Yeti sensor."""
    async_add_entities(
        GoalZeroBinarySensor(
            hass.data[DOMAIN][entry.entry_id],
            description,
        )
        for description in BINARY_SENSOR_TYPES
    )


class GoalZeroBinarySensor(GoalZeroEntity, BinarySensorEntity):
    """Representation of a Goal Zero Yeti sensor."""

    @property
    def is_on(self) -> bool:
        """Return True if the service is on."""
        return cast(bool, self._api.data[self.entity_description.key] == 1)
