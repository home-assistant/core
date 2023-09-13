"""Support for Aqualink pool feature switches."""
from __future__ import annotations

from typing import Any

from iaqualink.device import AqualinkSwitch

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AqualinkEntity, refresh_system
from .const import DOMAIN as AQUALINK_DOMAIN
from .utils import await_or_reraise

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkSwitch(dev))
    async_add_entities(devs, True)


class HassAqualinkSwitch(AqualinkEntity, SwitchEntity):
    """Representation of a switch."""

    def __init__(self, dev: AqualinkSwitch) -> None:
        """Initialize AquaLink switch."""
        super().__init__(dev)
        name = self._attr_name = dev.label
        if name == "Cleaner":
            self._attr_icon = "mdi:robot-vacuum"
        elif name == "Waterfall" or name.endswith("Dscnt"):
            self._attr_icon = "mdi:fountain"
        elif name.endswith("Pump") or name.endswith("Blower"):
            self._attr_icon = "mdi:fan"
        if name.endswith("Heater"):
            self._attr_icon = "mdi:radiator"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on or not."""
        return self.dev.is_on

    @refresh_system
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await await_or_reraise(self.dev.turn_on())

    @refresh_system
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await await_or_reraise(self.dev.turn_off())
