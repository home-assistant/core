"""Platform to retrieve uptime for Home Assistant."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

DEFAULT_NAME = "Uptime"

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_UNIT_OF_MEASUREMENT),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_UNIT_OF_MEASUREMENT, default="days"): vol.All(
                cv.string, vol.In(["minutes", "hours", "days", "seconds"])
            ),
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the uptime sensor platform."""
    name = config[CONF_NAME]

    async_add_entities([UptimeSensor(name)], True)


class UptimeSensor(SensorEntity):
    """Representation of an uptime sensor."""

    def __init__(self, name: str) -> None:
        """Initialize the uptime sensor."""
        self._attr_name: str = name
        self._attr_device_class: str = DEVICE_CLASS_TIMESTAMP
        self._attr_should_poll: bool = False
        self._attr_native_value = dt_util.utcnow()
