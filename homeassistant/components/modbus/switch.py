"""Support for Modbus switches."""

from typing import Any, override

import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_SWITCHES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import ModbusToggleEntity
from .modbus import get_hub
from .validators import BASE_SWITCH_SCHEMA

SWITCH_SCHEMA = BASE_SWITCH_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): SWITCH_DEVICE_CLASSES_SCHEMA,
    }
)

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


class ModbusSwitch(ModbusToggleEntity, SwitchEntity):
    """Base class representing a Modbus switch."""

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set switch on."""
        await self.async_turn(self.command_on)
