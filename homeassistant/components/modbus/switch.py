"""Support for Modbus switches."""
from abc import ABC
import logging
from typing import Any, Dict, Optional

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_NAME,
    CONF_SLAVE,
    STATE_ON,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import ModbusHub
from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COILS,
    CONF_HUB,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY_REGISTER,
    CONF_VERIFY_STATE,
    DEFAULT_HUB,
    MODBUS_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


REGISTERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND_OFF): cv.positive_int,
        vol.Required(CONF_COMMAND_ON): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_REGISTER): cv.positive_int,
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_REGISTER_TYPE, default=CALL_TYPE_REGISTER_HOLDING): vol.In(
            [CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]
        ),
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_STATE_OFF): cv.positive_int,
        vol.Optional(CONF_STATE_ON): cv.positive_int,
        vol.Optional(CONF_VERIFY_REGISTER): cv.positive_int,
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
    """Read configuration and create Modbus switches."""
    switches = []
    if CONF_COILS in config:
        for coil in config[CONF_COILS]:
            hub: ModbusHub = hass.data[MODBUS_DOMAIN][coil[CONF_HUB]]
            switches.append(ModbusCoilSwitch(hub, coil))
    if CONF_REGISTERS in config:
        for register in config[CONF_REGISTERS]:
            hub: ModbusHub = hass.data[MODBUS_DOMAIN][register[CONF_HUB]]
            switches.append(ModbusRegisterSwitch(hub, register))

    async_add_entities(switches)


class ModbusBaseSwitch(ToggleEntity, RestoreEntity, ABC):
    """Base class representing a Modbus switch."""

    def __init__(self, hub: ModbusHub, config: Dict[str, Any]):
        """Initialize the switch."""
        self._hub: ModbusHub = hub
        self._name = config[CONF_NAME]
        self._slave = config.get(CONF_SLAVE)
        self._is_on = None
        self._available = True

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if not state:
            return
        self._is_on = state.state == STATE_ON

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available


class ModbusCoilSwitch(ModbusBaseSwitch, SwitchEntity):
    """Representation of a Modbus coil switch."""

    def __init__(self, hub: ModbusHub, config: Dict[str, Any]):
        """Initialize the coil switch."""
        super().__init__(hub, config)
        self._coil = config[CALL_TYPE_COIL]

    def turn_on(self, **kwargs):
        """Set switch on."""
        self._write_coil(self._coil, True)
        self._is_on = True

    def turn_off(self, **kwargs):
        """Set switch off."""
        self._write_coil(self._coil, False)
        self._is_on = False

    def update(self):
        """Update the state of the switch."""
        self._is_on = self._read_coil(self._coil)

    def _read_coil(self, coil) -> bool:
        """Read coil using the Modbus hub slave."""
        try:
            result = self._hub.read_coils(self._slave, coil, 1)
        except ConnectionException:
            self._available = False
            return False

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return False

        self._available = True
        # bits[0] select the lowest bit in result,
        # is_on for a binary_sensor is true if the bit is 1
        # The other bits are not considered.
        return bool(result.bits[0] & 1)

    def _write_coil(self, coil, value):
        """Write coil using the Modbus hub slave."""
        try:
            self._hub.write_coil(self._slave, coil, value)
        except ConnectionException:
            self._available = False
            return

        self._available = True


class ModbusRegisterSwitch(ModbusBaseSwitch, SwitchEntity):
    """Representation of a Modbus register switch."""

    def __init__(self, hub: ModbusHub, config: Dict[str, Any]):
        """Initialize the register switch."""
        super().__init__(hub, config)
        self._register = config[CONF_REGISTER]
        self._command_on = config[CONF_COMMAND_ON]
        self._command_off = config[CONF_COMMAND_OFF]
        self._state_on = config.get(CONF_STATE_ON, self._command_on)
        self._state_off = config.get(CONF_STATE_OFF, self._command_off)
        self._verify_state = config[CONF_VERIFY_STATE]
        self._verify_register = config.get(CONF_VERIFY_REGISTER, self._register)
        self._register_type = config[CONF_REGISTER_TYPE]
        self._available = True
        self._is_on = None

    def turn_on(self, **kwargs):
        """Set switch on."""

        # Only holding register is writable
        if self._register_type == CALL_TYPE_REGISTER_HOLDING:
            self._write_register(self._command_on)
            if not self._verify_state:
                self._is_on = True

    def turn_off(self, **kwargs):
        """Set switch off."""

        # Only holding register is writable
        if self._register_type == CALL_TYPE_REGISTER_HOLDING:
            self._write_register(self._command_off)
            if not self._verify_state:
                self._is_on = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def update(self):
        """Update the state of the switch."""
        if not self._verify_state:
            return

        value = self._read_register()
        if value == self._state_on:
            self._is_on = True
        elif value == self._state_off:
            self._is_on = False
        elif value is not None:
            _LOGGER.error(
                "Unexpected response from hub %s, slave %s register %s, got 0x%2x",
                self._hub.name,
                self._slave,
                self._register,
                value,
            )

    def _read_register(self) -> Optional[int]:
        try:
            if self._register_type == CALL_TYPE_REGISTER_INPUT:
                result = self._hub.read_input_registers(
                    self._slave, self._verify_register, 1
                )
            else:
                result = self._hub.read_holding_registers(
                    self._slave, self._verify_register, 1
                )
        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        self._available = True

        return int(result.registers[0])

    def _write_register(self, value):
        """Write holding register using the Modbus hub slave."""
        try:
            self._hub.write_register(self._slave, self._register, value)
        except ConnectionException:
            self._available = False
            return

        self._available = True
