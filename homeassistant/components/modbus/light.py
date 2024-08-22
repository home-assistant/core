"""Support for Modbus lights."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.const import CONF_LIGHTS, CONF_NAME

from . import get_hub
from .base_platform import BaseSwitch

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

    from .modbus import ModbusHub

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus lights."""
    if discovery_info is None:
        return

    lights = []
    for entry in discovery_info[CONF_LIGHTS]:
        hub: ModbusHub = get_hub(hass, discovery_info[CONF_NAME])
        lights.append(ModbusLight(hass, hub, entry))
    async_add_entities(lights)


class ModbusLight(BaseSwitch, LightEntity):
    """Class representing a Modbus light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set light on."""
        await self.async_turn(self.command_on)
