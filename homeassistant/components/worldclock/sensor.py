"""Support for showing the time in a different time zone."""
from __future__ import annotations

from datetime import tzinfo

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, CONF_TIME_ZONE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

CONF_TIME_FORMAT = "time_format"

DEFAULT_NAME = "Worldclock Sensor"
DEFAULT_TIME_STR_FORMAT = "%H:%M"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TIME_ZONE): cv.time_zone,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIME_FORMAT, default=DEFAULT_TIME_STR_FORMAT): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the World clock sensor."""
    time_zone = dt_util.get_time_zone(config[CONF_TIME_ZONE])
    async_add_entities(
        [
            WorldClockSensor(
                time_zone,
                config[CONF_NAME],
                config[CONF_TIME_FORMAT],
            )
        ],
        True,
    )


class WorldClockSensor(SensorEntity):
    """Representation of a World clock sensor."""

    _attr_icon = "mdi:clock"

    def __init__(self, time_zone: tzinfo | None, name: str, time_format: str) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        self._time_zone = time_zone
        self._time_format = time_format

    async def async_update(self) -> None:
        """Get the time and updates the states."""
        self._attr_native_value = dt_util.now(time_zone=self._time_zone).strftime(
            self._time_format
        )
