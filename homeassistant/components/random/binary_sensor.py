"""Support for showing random states."""

from __future__ import annotations

from collections.abc import Mapping
from random import getrandbits
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DEFAULT_NAME = "Random binary sensor"

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Random binary sensor."""

    async_add_entities([RandomBinarySensor(config)], True)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    async_add_entities(
        [RandomBinarySensor(config_entry.options, config_entry.entry_id)], True
    )


class RandomBinarySensor(BinarySensorEntity):
    """Representation of a Random binary sensor."""

    _attr_translation_key = "random"

    def __init__(self, config: Mapping[str, Any], entry_id: str | None = None) -> None:
        """Initialize the Random binary sensor."""
        self._attr_name = config[CONF_NAME]
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_unique_id = entry_id

    async def async_update(self) -> None:
        """Get new state and update the sensor's state."""

        self._attr_is_on = bool(getrandbits(1))
