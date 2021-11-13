"""Provides a binary sensor which gets its values from a TCP socket."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import HOST_SCHEMA
from .common import TcpEntity
from .const import CONF_VALUE_ON


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the TCP binary sensor."""
    if discovery_info is None:
        return

    host_config = {key: discovery_info[key] for key in HOST_SCHEMA.schema.keys()}
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
