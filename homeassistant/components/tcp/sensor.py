"""Support for TCP socket based sensors."""
from __future__ import annotations

from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import TCP_PLATFORM_SCHEMA, TcpSensor

PLATFORM_SCHEMA: Final = TCP_PLATFORM_SCHEMA


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the TCP Sensor."""
    add_entities([TcpSensor(hass, config)])
