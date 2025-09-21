"""Support for Modbus switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SWITCHES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import get_hub
from .entity import ModbusToggleEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climates."""
    if CONF_SWITCHES not in config_entry.data:
        return

    hub = get_hub(hass, config_entry.data[CONF_NAME])
    async_add_entities(
        ModbusSwitch(hass, hub, config) for config in config_entry.data[CONF_SWITCHES]
    )


class ModbusSwitch(ModbusToggleEntity, SwitchEntity):
    """Base class representing a Modbus switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set switch on."""
        await self.async_turn(self.command_on)
