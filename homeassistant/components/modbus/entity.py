"""Base implementation for all modbus platforms."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
import copy
from datetime import datetime, timedelta
import struct
from typing import Any, cast

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COUNT,
    CONF_DELAY,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_UNIQUE_ID,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    _LOGGER,
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_COILS,
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    CALL_TYPE_X_COILS,
    CALL_TYPE_X_REGISTER_HOLDINGS,
    CONF_DATA_TYPE,
    CONF_DEVICE_ADDRESS,
    CONF_INPUT_TYPE,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_NAN_VALUE,
    CONF_PRECISION,
    CONF_SLAVE_COUNT,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_VERIFY,
    CONF_VIRTUAL_COUNT,
    CONF_WRITE_TYPE,
    CONF_ZERO_SUPPRESS,
    DEFAULT_OFFSET,
    DEFAULT_SCALE,
    SIGNAL_STOP_ENTITY,
    DataType,
)
from .modbus import ModbusHub


class ModbusBaseEntity(Entity):
    """Base for readonly platforms."""

    _value: str | None = None
    _attr_should_poll = False
    _attr_available = True
    _attr_unit_of_measurement = None

    def __init__(
        self, hass: HomeAssistant, hub: ModbusHub, entry: dict[str, Any]
    ) -> None:
        """Initialize the Modbus binary sensor."""

        self._hub = hub
        if (conf_slave := entry.get(CONF_SLAVE)) is not None:
            self._device_address = conf_slave
        else:
            self._device_address = entry.get(CONF_DEVICE_ADDRESS, 1)
        self._address = int(entry[CONF_ADDRESS])
        self._input_type = entry[CONF_INPUT_TYPE]
        self._scan_interval = int(entry[CONF_SCAN_INTERVAL])
        self._cancel_call: Callable[[], None] | None = None
        self._attr_unique_id = entry.get(CONF_UNIQUE_ID)
        self._attr_name = entry[CONF_NAME]
        self._attr_device_class = entry.get(CONF_DEVICE_CLASS)

        self._min_value = entry.get(CONF_MIN_VALUE)
        self._max_value = entry.get(CONF_MAX_VALUE)
        self._nan_value = entry.get(CONF_NAN_VALUE)
        self._zero_suppress = entry.get(CONF_ZERO_SUPPRESS)

    @abstractmethod
    async def _async_update(self) -> None:
        """Virtual function to be overwritten."""

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the entity state."""
        await self.async_local_update(cancel_pending_update=True)

    async def async_local_update(
        self, now: datetime | None = None, cancel_pending_update: bool = False
    ) -> None:
        """Update the entity state."""
        if cancel_pending_update and self._cancel_call:
            self._cancel_call()
        await self._async_update()
        self.async_write_ha_state()
        if self._scan_interval > 0:
            self._cancel_call = async_call_later(
                self.hass,
                timedelta(seconds=self._scan_interval),
                self.async_local_update,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Remove entity from hass."""
        self.async_disable()

    @callback
    def async_disable(self) -> None:
        """Remote stop entity."""
        _LOGGER.info(f"hold entity {self._attr_name}")
        if self._cancel_call:
            self._cancel_call()
            self._cancel_call = None
        self._attr_available = False

    async def async_await_connection(self, _now: Any) -> None:
        """Wait for first connect."""
        await self._hub.event_connected.wait()
        await self.async_local_update(cancel_pending_update=True)

    async def async_base_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_on_remove(
            async_call_later(
                self.hass,
                self._hub.config_delay + 0.1,
                self.async_await_connection,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_STOP_ENTITY, self.async_disable)
        )


class ModbusStructEntity(ModbusBaseEntity, RestoreEntity):
    """Base class representing a sensor/climate."""

    def __init__(self, hass: HomeAssistant, hub: ModbusHub, config: dict) -> None:
        """Initialize the switch."""
        super().__init__(hass, hub, config)
        self._swap = config[CONF_SWAP]
        self._data_type = config[CONF_DATA_TYPE]
        self._structure: str = config[CONF_STRUCTURE]
        self._slave_count = config.get(CONF_SLAVE_COUNT) or config.get(
            CONF_VIRTUAL_COUNT, 0
        )
        self._slave_size = self._count = config[CONF_COUNT]
        self._value_is_int: bool = self._data_type in (
            DataType.INT16,
            DataType.INT32,
            DataType.INT64,
            DataType.UINT16,
            DataType.UINT32,
            DataType.UINT64,
        )
        if not self._value_is_int:
            self._precision = config.get(CONF_PRECISION, 2)
        else:
            self._precision = config.get(CONF_PRECISION, 0)

    def _swap_registers(self, registers: list[int], slave_count: int) -> list[int]:
        """Do swap as needed."""
        if slave_count:
            swapped = []
            for i in range(self._slave_count + 1):
                inx = i * self._slave_size
                inx2 = inx + self._slave_size
                swapped.extend(self._swap_registers(registers[inx:inx2], 0))
            return swapped
        if self._swap in (CONF_SWAP_BYTE, CONF_SWAP_WORD_BYTE):
            # convert [12][34] --> [21][43]
            for i, register in enumerate(registers):
                registers[i] = int.from_bytes(
                    register.to_bytes(2, byteorder="little"),
                    byteorder="big",
                    signed=False,
                )
        if self._swap in (CONF_SWAP_WORD, CONF_SWAP_WORD_BYTE):
            # convert [12][34] ==> [34][12]
            registers.reverse()
        return registers

    def __process_raw_value(
        self,
        entry: float | bytes,
        scale: float = DEFAULT_SCALE,
        offset: float = DEFAULT_OFFSET,
    ) -> str | None:
        """Process value from sensor with NaN handling, scaling, offset, min/max etc."""
        if self._nan_value is not None and entry in (self._nan_value, -self._nan_value):
            return None
        if isinstance(entry, bytes):
            return entry.decode()
        if entry != entry:  # noqa: PLR0124
            # NaN float detection replace with None
            return None
        val: float | int = scale * entry + offset
        if self._min_value is not None and val < self._min_value:
            val = self._min_value
        if self._max_value is not None and val > self._max_value:
            val = self._max_value
        if self._zero_suppress is not None and abs(val) <= self._zero_suppress:
            return "0"
        if self._precision == 0:
            return str(round(val))
        return f"{float(val):.{self._precision}f}"

    def unpack_structure_result(
        self,
        registers: list[int],
        scale: float = DEFAULT_SCALE,
        offset: float = DEFAULT_OFFSET,
    ) -> str | None:
        """Convert registers to proper result."""

        if self._swap:
            registers = self._swap_registers(
                copy.deepcopy(registers), self._slave_count
            )
        byte_string = b"".join([x.to_bytes(2, byteorder="big") for x in registers])
        if self._data_type == DataType.STRING:
            return byte_string.decode()
        if byte_string == b"nan\x00":
            return None

        try:
            val = struct.unpack(self._structure, byte_string)
        except struct.error as err:
            recv_size = len(registers) * 2
            msg = f"Received {recv_size} bytes, unpack error {err}"
            _LOGGER.error(msg)
            return None
        if len(val) > 1:
            # Apply scale, precision, limits to floats and ints
            v_result = []
            for entry in val:
                v_temp = self.__process_raw_value(entry, scale, offset)
                if self._data_type != DataType.CUSTOM:
                    v_result.append(str(v_temp))
                else:
                    v_result.append(str(v_temp) if v_temp is not None else "0")
            return ",".join(map(str, v_result))

        # Apply scale, precision, limits to floats and ints
        return self.__process_raw_value(val[0], scale, offset)


class ModbusToggleEntity(ModbusBaseEntity, ToggleEntity, RestoreEntity):
    """Base class representing a Modbus switch."""

    def __init__(self, hass: HomeAssistant, hub: ModbusHub, config: dict) -> None:
        """Initialize the switch."""
        config[CONF_INPUT_TYPE] = ""
        super().__init__(hass, hub, config)
        self._attr_is_on = False
        convert = {
            CALL_TYPE_REGISTER_HOLDING: (
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_WRITE_REGISTER,
            ),
            CALL_TYPE_DISCRETE: (
                CALL_TYPE_DISCRETE,
                None,
            ),
            CALL_TYPE_REGISTER_INPUT: (
                CALL_TYPE_REGISTER_INPUT,
                None,
            ),
            CALL_TYPE_COIL: (CALL_TYPE_COIL, CALL_TYPE_WRITE_COIL),
            CALL_TYPE_X_COILS: (CALL_TYPE_COIL, CALL_TYPE_WRITE_COILS),
            CALL_TYPE_X_REGISTER_HOLDINGS: (
                CALL_TYPE_REGISTER_HOLDING,
                CALL_TYPE_WRITE_REGISTERS,
            ),
        }
        self._write_type = cast(str, convert[config[CONF_WRITE_TYPE]][1])
        self.command_on = config[CONF_COMMAND_ON]
        self._command_off = config[CONF_COMMAND_OFF]
        if CONF_VERIFY in config:
            if config[CONF_VERIFY] is None:
                config[CONF_VERIFY] = {}
            self._verify_active = True
            self._verify_delay = config[CONF_VERIFY].get(CONF_DELAY, 0)
            self._verify_address = config[CONF_VERIFY].get(
                CONF_ADDRESS, config[CONF_ADDRESS]
            )
            self._verify_type = convert[
                config[CONF_VERIFY].get(CONF_INPUT_TYPE, config[CONF_WRITE_TYPE])
            ][0]
            self._state_on = config[CONF_VERIFY].get(CONF_STATE_ON, [self.command_on])
            self._state_off = config[CONF_VERIFY].get(
                CONF_STATE_OFF, [self._command_off]
            )
        else:
            self._verify_active = False

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if state := await self.async_get_last_state():
            if state.state == STATE_ON:
                self._attr_is_on = True
            elif state.state == STATE_OFF:
                self._attr_is_on = False
        await super().async_added_to_hass()

    async def async_turn(self, command: int) -> None:
        """Evaluate switch result."""
        result = await self._hub.async_pb_call(
            self._device_address, self._address, command, self._write_type
        )
        if result is None:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        if not self._verify_active:
            self._attr_is_on = command == self.command_on
            self.async_write_ha_state()
            return

        if self._verify_delay:
            if self._cancel_call:
                self._cancel_call()
                self._cancel_call = None
            self._cancel_call = async_call_later(
                self.hass, self._verify_delay, self.async_update
            )
            return
        await self.async_local_update(cancel_pending_update=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set switch off."""
        await self.async_turn(self._command_off)

    async def _async_update(self) -> None:
        """Update the entity state."""
        if not self._verify_active:
            self._attr_available = True
            return

        # do not allow multiple active calls to the same platform
        result = await self._hub.async_pb_call(
            self._device_address, self._verify_address, 1, self._verify_type
        )
        if result is None:
            self._attr_available = False
            return

        self._attr_available = True
        if self._verify_type in (CALL_TYPE_COIL, CALL_TYPE_DISCRETE):
            self._attr_is_on = bool(result.bits[0] & 1)
        else:
            value = int(result.registers[0])
            if value in self._state_on:
                self._attr_is_on = True
            elif value in self._state_off:
                self._attr_is_on = False
            elif value is not None:
                _LOGGER.error(
                    (
                        "Unexpected response from modbus device slave %s register %s,"
                        " got 0x%2x"
                    ),
                    self._device_address,
                    self._verify_address,
                    value,
                )
