"""Support for Modbus switches."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_SWITCHES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ModbusToggleEntity
from .modbus import get_hub
from .validators import BASE_SWITCH_SCHEMA

SWITCH_SCHEMA = BASE_SWITCH_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): SWITCH_DEVICE_CLASSES_SCHEMA,
    }
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Modbus switches from a config entry."""
    hub = get_hub(hass, config_entry.data[CONF_NAME])
    async_add_entities(
        ModbusSwitch(hass, hub, config)
        for config in config_entry.data.get(CONF_SWITCHES, [])
    )


class ModbusSwitch(ModbusToggleEntity, SwitchEntity):
    """Base class representing a Modbus switch."""

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set switch on."""
        await self.async_turn(self.command_on)
