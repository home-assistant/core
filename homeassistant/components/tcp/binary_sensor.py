"""Provides a binary sensor which gets its values from a TCP socket."""
from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_VALUE_ON
from .sensor import PLATFORM_SCHEMA as TCP_PLATFORM_SCHEMA, TcpSensor

PLATFORM_SCHEMA: Final = TCP_PLATFORM_SCHEMA


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the TCP binary sensor."""
    add_entities([TcpBinarySensor(hass, config)])


class TcpBinarySensor(BinarySensorEntity, TcpSensor):
    """A binary sensor which is on when its state == CONF_VALUE_ON."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state == self._config[CONF_VALUE_ON]
