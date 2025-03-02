"""Support for Modbus lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.const import CONF_LIGHTS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .entity import BaseSwitch

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus lights."""
    if discovery_info is None or not (lights := discovery_info[CONF_LIGHTS]):
        return
    hub = get_hub(hass, discovery_info[CONF_NAME])
    async_add_entities(ModbusLight(hass, hub, config) for config in lights)


class ModbusLight(BaseSwitch, LightEntity):
    """Class representing a Modbus light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set light on."""
        await self.async_turn(self.command_on)
