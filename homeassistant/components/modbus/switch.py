"""Support for Modbus switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME, CONF_SWITCHES
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
    """Read configuration and create Modbus switches."""
    if discovery_info is None or not (switches := discovery_info[CONF_SWITCHES]):
        return
    hub = get_hub(hass, discovery_info[CONF_NAME])
    async_add_entities(ModbusSwitch(hass, hub, config) for config in switches)


class ModbusSwitch(BaseSwitch, SwitchEntity):
    """Base class representing a Modbus switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set switch on."""
        await self.async_turn(self.command_on)
