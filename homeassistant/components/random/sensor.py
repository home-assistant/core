"""Support for showing random numbers."""
from __future__ import annotations

from collections.abc import Mapping
from random import randrange
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_MAX, DEFAULT_MIN

ATTR_MAXIMUM = "maximum"
ATTR_MINIMUM = "minimum"

DEFAULT_NAME = "Random sensor"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""

    async_add_entities(
        [RandomSensor(config_entry.options, config_entry.entry_id)], True
    )


class RandomSensor(SensorEntity):
    """Representation of a Random number sensor."""

    _attr_icon = "mdi:hanger"
    _state: int | None = None

    def __init__(self, config: Mapping[str, Any], entry_id: str | None = None) -> None:
        """Initialize the Random sensor."""
        self._name = config.get(CONF_NAME)
        self._minimum = config.get(CONF_MINIMUM, DEFAULT_MIN)
        self._maximum = config.get(CONF_MAXIMUM, DEFAULT_MAX)
        self._unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        if entry_id:
            self._attr_unique_id = entry_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the attributes of the sensor."""
        return {ATTR_MAXIMUM: self._maximum, ATTR_MINIMUM: self._minimum}

    async def async_update(self) -> None:
        """Get a new number and updates the states."""

        self._state = randrange(self._minimum, self._maximum + 1)
