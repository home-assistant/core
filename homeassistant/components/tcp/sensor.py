"""Support for TCP socket based sensors."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .common import TCP_PLATFORM_SCHEMA, TcpEntity

PLATFORM_SCHEMA: Final = PARENT_PLATFORM_SCHEMA.extend(TCP_PLATFORM_SCHEMA)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the TCP Sensor."""
    add_entities([TcpSensor(hass, config)])


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
