"""Support for Modbus lights."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import LightEntity
from homeassistant.const import CONF_LIGHTS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .base_platform import BaseSwitch
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus lights."""
    if discovery_info is None:  # pragma: no cover
        return

    lights = []
    for entry in discovery_info[CONF_LIGHTS]:
        hub: ModbusHub = get_hub(hass, discovery_info[CONF_NAME])
        lights.append(ModbusLight(hub, entry))
    async_add_entities(lights)


class ModbusLight(BaseSwitch, LightEntity):
    """Class representing a Modbus light."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set light on."""
        await self.async_turn(self.command_on)
