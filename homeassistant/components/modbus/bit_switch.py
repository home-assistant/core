"""Support for Modbus switches."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    STATE_ON,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import DiscoveryInfoType, HomeAssistantType

from .bit_sensor import ModbusReadCache
from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_BIT_SWITCHES,
    CONF_COMMAND_BIT_NUMBER,
    CONF_INPUT_TYPE,
    CONF_STATUS_BIT_NUMBER,
    CONF_VERIFY_REGISTER,
    CONF_VERIFY_STATE,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)


def setup_bit_swithes(
    hass: HomeAssistantType,
    discovery_info: DiscoveryInfoType | None = None,
) -> [SwitchEntity]:
    """Modbus Bit Switches setup."""
    switches = []

    if discovery_info is None:
        return switches

    for entry in discovery_info.get(CONF_BIT_SWITCHES, []):
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        switches.append(ModbusRegisterBitSwitch(hub, entry))

    return switches


class ModbusBaseSwitch(SwitchEntity, RestoreEntity, ABC):
    """Base class representing a Modbus switch."""

    def __init__(self, hub: ModbusHub, config: dict[str, Any]):
        """Initialize the switch."""
        self._hub: ModbusHub = hub
        self._name = config[CONF_NAME]
        self._slave = config.get(CONF_SLAVE)
        self._register_type = config[CONF_INPUT_TYPE]
        self._is_on = None
        self._available = True
        self._scan_interval = timedelta(seconds=config[CONF_SCAN_INTERVAL])

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if state:
            self._is_on = state.state == STATE_ON

        async_track_time_interval(
            self.hass, lambda arg: self._update(), self._scan_interval
        )

    @abstractmethod
    def _update(self):
        """Update the entity state."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """

        # Handle polling directly in this entity
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def _read_register(self, address) -> int | None:
        try:
            if self._register_type == CALL_TYPE_REGISTER_INPUT:
                result = self._hub.read_input_registers(self._slave, address, 1)
            else:
                result = self._hub.read_holding_registers(self._slave, address, 1)

        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        self._available = True
        return int(result.registers[0])

    def _write_register(self, address, value):
        """Write holding register or coil using the Modbus hub slave."""
        try:
            self._hub.write_register(self._slave, address, value)
        except ConnectionException:
            self._available = False
            return False

        self._available = True
        return True


class ModbusRegisterBitSwitch(ModbusBaseSwitch, SwitchEntity):
    """Representation of a Modbus register switch."""

    def __init__(self, hub: ModbusHub, config: dict[str, Any]):
        """Initialize the register switch."""
        super().__init__(ModbusReadCache(hub), config)
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

        self._is_on = None

    def turn_on(self, **kwargs):
        """Set switch on."""
        # Only holding register is writable
        if self._register_type != CALL_TYPE_REGISTER_HOLDING:
            return
        register_value = self._read_register(self._verify_register)
        if register_value is None:
            self._available = False
            return
        if self._write_register(
            self._register, register_value | self._command_bit_mask
        ):
            self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Set switch off."""
        # Only holding register is writable
        if self._register_type != CALL_TYPE_REGISTER_HOLDING:
            return
        register_value = self._read_register(self._verify_register)
        if register_value is None:
            self._available = False
            return
        if self._write_register(
            self._register, register_value & ~self._command_bit_mask
        ):
            self._is_on = False
        self.schedule_update_ha_state()

    def _update(self):
        """Update the state of the switch."""
        if not self._verify_state:
            return
        value = self._read_register(self._verify_register)
        if value is not None:
            self._is_on = bool(value & self._status_bit_mask)
            self._available = True
        else:
            self._available = False
        self.schedule_update_ha_state()
