"""Support for Modbus lights."""
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA, LightEntity
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_NAME, CONF_SLAVE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CONF_COILS,
    CONF_HUB,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_VERIFY_STATE,
    DEFAULT_HUB,
)
from .switch import ModbusCoilSwitch, ModbusRegisterSwitch

_LOGGER = logging.getLogger(__name__)

REGISTERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_REGISTER): cv.positive_int,
        vol.Optional(CONF_COMMAND_OFF, default=0): cv.positive_int,
        vol.Optional(CONF_COMMAND_ON, default=1): cv.positive_int,
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_VERIFY_STATE, default=True): cv.boolean,
    }
)

COILS_SCHEMA = vol.Schema(
    {
        vol.Required(CALL_TYPE_COIL): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
    }
)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_COILS, CONF_REGISTERS),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_COILS): [COILS_SCHEMA],
            vol.Optional(CONF_REGISTERS): [REGISTERS_SCHEMA],
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
):
    """Read configuration and create Modbus lights."""
    if CONF_COILS in config:
        for coil in config[CONF_COILS]:
            async_add_entities([ModbusCoilLight(hass, coil)])
    if CONF_REGISTERS in config:
        for register in config[CONF_REGISTERS]:
            async_add_entities([ModbusRegisterLight(hass, register)])


class ModbusCoilLight(ModbusCoilSwitch, LightEntity):
    """Representation of a Modbus coil light."""


class ModbusRegisterLight(ModbusRegisterSwitch, LightEntity):
    """Representation of a Modbus register light."""

    def __init__(self, hass: HomeAssistantType, config: Dict[str, Any]):
        """Initialize the register fan."""
        config[CONF_REGISTER_TYPE] = CALL_TYPE_REGISTER_HOLDING
        super().__init__(hass, config)
