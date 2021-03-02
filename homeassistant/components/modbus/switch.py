"""Support for Modbus switches."""
from abc import ABC
import logging
from typing import Any, Dict, Optional

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_NAME,
    CONF_SLAVE,
    CONF_SWITCHES,
    STATE_ON,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_BIT_SWITCHES,
    CONF_COILS,
    CONF_COMMAND_BIT_NUMBER,
    CONF_HUB,
    CONF_INPUT_TYPE,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_STATUS_BIT_NUMBER,
    CONF_VERIFY_REGISTER,
    CONF_VERIFY_STATE,
    DEFAULT_HUB,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

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

    #  check for old config:
    if discovery_info is None:
        _LOGGER.warning(
            "switch configuration depreciated, will be removed in a future release"
        )
        discovery_info = {
            CONF_NAME: "noName",
            CONF_SWITCHES: [],
        }
        if CONF_COILS in config:
            discovery_info[CONF_SWITCHES].extend(config[CONF_COILS])
        if CONF_REGISTERS in config:
            discovery_info[CONF_SWITCHES].extend(config[CONF_REGISTERS])
        for entry in discovery_info[CONF_SWITCHES]:
            if CALL_TYPE_COIL in entry:
                entry[CONF_ADDRESS] = entry[CALL_TYPE_COIL]
                entry[CONF_INPUT_TYPE] = CALL_TYPE_COIL
                del entry[CALL_TYPE_COIL]
            if CONF_REGISTER in entry:
                entry[CONF_ADDRESS] = entry[CONF_REGISTER]
                del entry[CONF_REGISTER]
                if CONF_REGISTER_TYPE in entry:
                    entry[CONF_INPUT_TYPE] = entry[CONF_REGISTER_TYPE]
                    del entry[CONF_REGISTER_TYPE]
        config = None

    for entry in discovery_info.get(CONF_SWITCHES, []):
        if CONF_HUB in entry:
            # from old config!
            discovery_info[CONF_NAME] = entry[CONF_HUB]
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        if entry[CONF_INPUT_TYPE] == CALL_TYPE_COIL:
            switches.append(ModbusCoilSwitch(hub, entry))
        else:
            switches.append(ModbusRegisterSwitch(hub, entry))

    for entry in discovery_info.get(CONF_BIT_SWITCHES, []):
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        switches.append(ModbusRegisterBitSwitch(hub, entry))

    async_add_entities(switches)


class ModbusBaseSwitch(ToggleEntity, RestoreEntity, ABC):
    """Base class representing a Modbus switch."""

    def __init__(self, hub: ModbusHub, config: Dict[str, Any]):
        """Initialize the switch."""
        self._hub: ModbusHub = hub
        self._name = config[CONF_NAME]
        self._slave = config.get(CONF_SLAVE)
        self._register_type = config[CONF_INPUT_TYPE]
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

    def _read_modbus(self, address) -> Optional[int]:
        try:
            if self._register_type == CALL_TYPE_REGISTER_INPUT:
                result = self._hub.read_input_registers(self._slave, address, 1)
            elif self._register_type == CALL_TYPE_REGISTER_HOLDING:
                result = self._hub.read_holding_registers(self._slave, address, 1)
            else:
                result = self._hub.read_coils(self._slave, address, 1)

        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        self._available = True

        if self._register_type == CALL_TYPE_COIL:
            # bits[0] select the lowest bit in result,
            # is_on for a binary_sensor is true if the bit is 1
            # The other bits are not considered.
            return bool(result.bits[0] & 1)

        return int(result.registers[0])

    def _write_modbus(self, address, value):
        """Write holding register or coil using the Modbus hub slave."""
        try:
            if self._register_type == CALL_TYPE_COIL:
                self._hub.write_coil(self._slave, address, value)
            else:
                self._hub.write_register(self._slave, address, value)
        except ConnectionException:
            self._available = False
            return

        self._available = True


class ModbusCoilSwitch(ModbusBaseSwitch, SwitchEntity):
    """Representation of a Modbus coil switch."""

    def __init__(self, hub: ModbusHub, config: Dict[str, Any]):
        """Initialize the coil switch."""
        super().__init__(hub, config)
        self._coil = config[CONF_ADDRESS]

    def turn_on(self, **kwargs):
        """Set switch on."""
        self._write_modbus(self._coil, True)
        self._is_on = True

    def turn_off(self, **kwargs):
        """Set switch off."""
        self._write_modbus(self._coil, False)
        self._is_on = False

    def update(self):
        """Update the state of the switch."""
        self._is_on = self._read_modbus(self._coil)


class ModbusRegisterSwitch(ModbusBaseSwitch, SwitchEntity):
    """Representation of a Modbus register switch."""

    def __init__(self, hub: ModbusHub, config: Dict[str, Any]):
        """Initialize the register switch."""
        super().__init__(hub, config)
        self._register = config[CONF_ADDRESS]
        self._command_on = config[CONF_COMMAND_ON]
        self._command_off = config[CONF_COMMAND_OFF]
        self._state_on = config.get(CONF_STATE_ON, self._command_on)
        self._state_off = config.get(CONF_STATE_OFF, self._command_off)
        self._verify_state = config[CONF_VERIFY_STATE]
        self._verify_register = config.get(CONF_VERIFY_REGISTER, self._register)
        self._available = True
        self._is_on = None

    def turn_on(self, **kwargs):
        """Set switch on."""
        # Only holding register is writable
        if self._register_type != CALL_TYPE_REGISTER_HOLDING:
            return
        self._write_modbus(self._register, self._command_on)
        if not self._verify_state:
            self._is_on = True

    def turn_off(self, **kwargs):
        """Set switch off."""
        # Only holding register is writable
        if self._register_type != CALL_TYPE_REGISTER_HOLDING:
            return
        self._write_modbus(self._register, self._command_off)
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

        value = self._read_modbus(self._verify_register)
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


class ModbusRegisterBitSwitch(ModbusBaseSwitch, SwitchEntity):
    """Representation of a Modbus register switch."""

    def __init__(self, hub: ModbusHub, config: Dict[str, Any]):
        """Initialize the register switch."""
        super().__init__(hub, config)
        self._register = config[CONF_ADDRESS]
        self._verify_state = config[CONF_VERIFY_STATE]
        self._verify_register = config.get(CONF_VERIFY_REGISTER, self._register)
        self._register_type = config[CONF_INPUT_TYPE]

        command_bit_numer = int(config[CONF_COMMAND_BIT_NUMBER])
        status_bit_numer = int(config.get(CONF_STATUS_BIT_NUMBER, command_bit_numer))
        assert 0 <= command_bit_numer < 16
        assert 0 <= status_bit_numer < 16

        self._command_bit_mask = 1 << command_bit_numer
        self._status_bit_mask = 1 << status_bit_numer

        self._available = False
        self._is_on = None

    def turn_on(self, **kwargs):
        """Set switch on."""
        # Only holding register is writable
        if self._register_type != CALL_TYPE_REGISTER_HOLDING:
            return
        register_value = self._read_modbus(self._verify_register)
        if register_value is None:
            self._available = False
            return
        self._write_modbus(self._register, register_value | self._command_bit_mask)
        if not self._verify_state:
            self._is_on = True

    def turn_off(self, **kwargs):
        """Set switch off."""
        # Only holding register is writable
        if self._register_type != CALL_TYPE_REGISTER_HOLDING:
            return
        register_value = self._read_modbus(self._verify_register)
        if register_value is None:
            self._available = False
            return
        self._write_modbus(self._register, register_value & ~self._command_bit_mask)
        if not self._verify_state:
            self._is_on = False

    def update(self):
        """Update the state of the switch."""
        if not self._verify_state:
            return
        value = self._read_modbus(self._verify_register)
        if value is None:
            self._available = False
            return
        self._is_on = bool(value & self._status_bit_mask)
        self._available = True
