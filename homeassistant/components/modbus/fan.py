"""Support for Modbus fans."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .base_platform import BaseSwitch
from .const import CONF_FANS
from .modbus import ModbusHub

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus fans."""
    if discovery_info is None:
        return
    fans = []

    for entry in discovery_info[CONF_FANS]:
        hub: ModbusHub = get_hub(hass, discovery_info[CONF_NAME])
        fans.append(ModbusFan(hass, hub, entry))
    async_add_entities(fans)


class ModbusFan(BaseSwitch, FanEntity):
    """Class representing a Modbus fan."""

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Set fan on."""
        await self.async_turn(self.command_on)

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on.

        This is needed due to the ongoing conversion of fan.
        """
        return self._attr_is_on
