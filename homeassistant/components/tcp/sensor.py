"""Support for TCP socket based sensors."""
from __future__ import annotations

from typing import Final

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import HOST_SCHEMA, SENSOR_SCHEMA
from .common import TCP_PLATFORM_SCHEMA, TcpEntity

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
    """Set up the TCP Sensor."""
    if discovery_info is None:
        # Deprecated branch
        host_config = {
            key: config[key] for key in HOST_SCHEMA.schema.keys() if key in config
        }
        entity_config = {
            key: config[key] for key in SENSOR_SCHEMA.schema.keys() if key in config
        }
        entities = [TcpSensor(hass, entity_config, host_config)]
    else:
        host_config = {
            key: discovery_info[key]
            for key in HOST_SCHEMA.schema.keys()
            if key in discovery_info
        }
        entities = [
            TcpSensor(hass, entity_config, host_config)
            for entity_config in discovery_info["sensors"]
        ]
    async_add_entities(entities)


class TcpSensor(TcpEntity, SensorEntity):
    """Implementation of a TCP socket based sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        return self._config[CONF_UNIT_OF_MEASUREMENT]
