"""Provides a binary sensor which gets its values from a TCP socket."""
from __future__ import annotations

from typing import Final

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import BINARY_SENSOR_SCHEMA, HOST_SCHEMA
from .common import TCP_PLATFORM_SCHEMA, TcpEntity
from .const import CONF_VALUE_ON

PLATFORM_SCHEMA: Final = vol.All(
    *(
        cv.deprecated(key)
        for key in TCP_PLATFORM_SCHEMA.keys() | PARENT_PLATFORM_SCHEMA.schema.keys()
    ),
    PARENT_PLATFORM_SCHEMA.extend(TCP_PLATFORM_SCHEMA),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the TCP binary sensor."""
    if discovery_info is None:
        # Deprecated branch
        host_config = {
            key: config[key] for key in HOST_SCHEMA.schema.keys() if key in config
        }
        entity_config = {
            key: config[key]
            for key in BINARY_SENSOR_SCHEMA.schema.keys()
            if key in config
        }
        entities = [TcpBinarySensor(hass, entity_config, host_config)]
    else:
        host_config = {
            key: discovery_info[key]
            for key in HOST_SCHEMA.schema.keys()
            if key in discovery_info
        }
        entities = [
            TcpBinarySensor(hass, entity_config, host_config)
            for entity_config in discovery_info["binary_sensors"]
        ]

    async_add_entities(entities)


class TcpBinarySensor(TcpEntity, BinarySensorEntity):
    """A binary sensor which is on when its state == CONF_VALUE_ON."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state == self._config[CONF_VALUE_ON]
