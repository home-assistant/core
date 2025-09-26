"""Support for showing random numbers."""

from __future__ import annotations

from collections.abc import Mapping
from random import randrange
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_MAX, DEFAULT_MIN

ATTR_MAXIMUM = "maximum"
ATTR_MINIMUM = "minimum"

DEFAULT_NAME = "Random sensor"


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX): cv.positive_int,
        vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Random number sensor."""

    async_add_entities([RandomSensor(config)], True)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""

    async_add_entities(
        [RandomSensor(config_entry.options, config_entry.entry_id)], True
    )


class RandomSensor(SensorEntity):
    """Representation of a Random number sensor."""

    _attr_translation_key = "random"
    _unrecorded_attributes = frozenset({ATTR_MAXIMUM, ATTR_MINIMUM})

    def __init__(self, config: Mapping[str, Any], entry_id: str | None = None) -> None:
        """Initialize the Random sensor."""
        self._attr_name = config[CONF_NAME]
        self._minimum = config[CONF_MINIMUM]
        self._maximum = config[CONF_MAXIMUM]
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_extra_state_attributes = {
            ATTR_MAXIMUM: self._maximum,
            ATTR_MINIMUM: self._minimum,
        }
        self._attr_unique_id = entry_id

    async def async_update(self) -> None:
        """Get a new number and update the state."""

        self._attr_native_value = randrange(self._minimum, self._maximum + 1)
