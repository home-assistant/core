"""Base implementation for all modbus platforms."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
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
    CONF_OFFSET,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_UNIQUE_ID,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
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
    CONF_INPUT_TYPE,
    CONF_LAZY_ERROR,
    CONF_MAX_VALUE,
    CONF_MIN_VALUE,
    CONF_NAN_VALUE,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_SLAVE_COUNT,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_NONE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_VERIFY,
    CONF_WRITE_TYPE,
    CONF_ZERO_SUPPRESS,
    SIGNAL_START_ENTITY,
    SIGNAL_STOP_ENTITY,
    DataType,
)
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


class BasePlatform(Entity):
    """Base for readonly platforms."""

    def __init__(self, hub: ModbusHub, entry: dict[str, Any]) -> None:
        """Initialize the Modbus binary sensor."""
        self._hub = hub
        self._slave = entry.get(CONF_SLAVE, 0)
        self._address = int(entry[CONF_ADDRESS])
        self._input_type = entry[CONF_INPUT_TYPE]
        self._value: str | None = None
        self._scan_interval = int(entry[CONF_SCAN_INTERVAL])
        self._call_active = False
        self._cancel_timer: Callable[[], None] | None = None
        self._cancel_call: Callable[[], None] | None = None

        self._attr_unique_id = entry.get(CONF_UNIQUE_ID)
        self._attr_name = entry[CONF_NAME]
        self._attr_should_poll = False
        self._attr_device_class = entry.get(CONF_DEVICE_CLASS)
        self._attr_available = True
        self._attr_unit_of_measurement = None
        self._lazy_error_count = entry[CONF_LAZY_ERROR]
        self._lazy_errors = self._lazy_error_count

        def get_optional_numeric_config(config_name: str) -> int | float | None:
            if (val := entry.get(config_name)) is None:
                return None
            assert isinstance(
                val, (float, int)
            ), f"Expected float or int but {config_name} was {type(val)}"
            return val

        self._min_value = get_optional_numeric_config(CONF_MIN_VALUE)
        self._max_value = get_optional_numeric_config(CONF_MAX_VALUE)
        self._nan_value = entry.get(CONF_NAN_VALUE, None)
        self._zero_suppress = get_optional_numeric_config(CONF_ZERO_SUPPRESS)

    @abstractmethod
    async def async_update(self, now: datetime | None = None) -> None:
        """Virtual function to be overwritten."""

    @callback
    def async_run(self) -> None:
        """Remote start entity."""
        self.async_hold(update=False)
        self._cancel_call = async_call_later(self.hass, 1, self.async_update)
        if self._scan_interval > 0:
            self._cancel_timer = async_track_time_interval(
                self.hass, self.async_update, timedelta(seconds=self._scan_interval)
            )
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def async_hold(self, update: bool = True) -> None:
        """Remote stop entity."""
        if self._cancel_call:
            self._cancel_call()
            self._cancel_call = None
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        if update:
            self._attr_available = False
            self.async_write_ha_state()

    async def async_base_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_run()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_STOP_ENTITY, self.async_hold)
        )
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_START_ENTITY, self.async_run)
        )


class BaseStructPlatform(BasePlatform, RestoreEntity):
    """Base class representing a sensor/climate."""

    def __init__(self, hub: ModbusHub, config: dict) -> None:
        """Initialize the switch."""
        super().__init__(hub, config)
        self._swap = config[CONF_SWAP]
        if self._swap == CONF_SWAP_NONE:
            self._swap = None
        self._data_type = config[CONF_DATA_TYPE]
        self._structure: str = config[CONF_STRUCTURE]
        self._precision = config[CONF_PRECISION]
        self._scale = config[CONF_SCALE]
        self._offset = config[CONF_OFFSET]
        self._slave_count = config.get(CONF_SLAVE_COUNT, 0)
        self._slave_size = self._count = config[CONF_COUNT]

    def _swap_registers(self, registers: list[int], slave_count: int) -> list[int]:
        """Do swap as needed."""
        if slave_count:
            swapped = []
            for i in range(0, self._slave_count + 1):
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

    def __process_raw_value(self, entry: float | int | str) -> float | int | str | None:
        """Process value from sensor with NaN handling, scaling, offset, min/max etc."""
        if self._nan_value and entry in (self._nan_value, -self._nan_value):
            return None
        val: float | int = self._scale * entry + self._offset
        if self._min_value is not None and val < self._min_value:
            return self._min_value
        if self._max_value is not None and val > self._max_value:
            return self._max_value
        if self._zero_suppress is not None and abs(val) <= self._zero_suppress:
            return 0
        return val

    def unpack_structure_result(self, registers: list[int]) -> str | None:
        """Convert registers to proper result."""

        if self._swap:
            registers = self._swap_registers(registers, self._slave_count)
        byte_string = b"".join([x.to_bytes(2, byteorder="big") for x in registers])
        if self._data_type == DataType.STRING:
            return byte_string.decode()

        try:
            val = struct.unpack(self._structure, byte_string)
        except struct.error as err:
            recv_size = len(registers) * 2
            msg = f"Received {recv_size} bytes, unpack error {err}"
            _LOGGER.error(msg)
            return None
        # Issue: https://github.com/home-assistant/core/issues/41944
        # If unpack() returns a tuple greater than 1, don't try to process the value.
        # Instead, return the values of unpack(...) separated by commas.
        if len(val) > 1:
            # Apply scale, precision, limits to floats and ints
            v_result = []
            for entry in val:
                v_temp = self.__process_raw_value(entry)

                # We could convert int to float, and the code would still work; however
                # we lose some precision, and unit tests will fail. Therefore, we do
                # the conversion only when it's absolutely necessary.
                if isinstance(v_temp, int) and self._precision == 0:
                    v_result.append(str(v_temp))
                elif v_temp is None:
                    v_result.append("")  # pragma: no cover
                elif v_temp != v_temp:  # noqa: PLR0124
                    # NaN float detection replace with None
                    v_result.append("nan")  # pragma: no cover
                else:
                    v_result.append(f"{float(v_temp):.{self._precision}f}")
            return ",".join(map(str, v_result))

        # Apply scale, precision, limits to floats and ints
        val_result = self.__process_raw_value(val[0])

        # We could convert int to float, and the code would still work; however
        # we lose some precision, and unit tests will fail. Therefore, we do
        # the conversion only when it's absolutely necessary.

        if val_result is None:
            return None
        # NaN float detection replace with None
        if val_result != val_result:  # noqa: PLR0124
            return None  # pragma: no cover
        if isinstance(val_result, int) and self._precision == 0:
            return str(val_result)
        if isinstance(val_result, str):
            if val_result == "nan":
                val_result = None  # pragma: no cover
            return val_result
        return f"{float(val_result):.{self._precision}f}"


class BaseSwitch(BasePlatform, ToggleEntity, RestoreEntity):
    """Base class representing a Modbus switch."""

    def __init__(self, hub: ModbusHub, config: dict) -> None:
        """Initialize the switch."""
        config[CONF_INPUT_TYPE] = ""
        super().__init__(hub, config)
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
            self._state_on = config[CONF_VERIFY].get(CONF_STATE_ON, self.command_on)
            self._state_off = config[CONF_VERIFY].get(CONF_STATE_OFF, self._command_off)
        else:
            self._verify_active = False

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if state := await self.async_get_last_state():
            self._attr_is_on = state.state == STATE_ON

    async def async_turn(self, command: int) -> None:
        """Evaluate switch result."""
        result = await self._hub.async_pb_call(
            self._slave, self._address, command, self._write_type
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
            async_call_later(self.hass, self._verify_delay, self.async_update)
        else:
            await self.async_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set switch off."""
        await self.async_turn(self._command_off)

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the entity state."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        if not self._verify_active:
            self._attr_available = True
            self.async_write_ha_state()
            return

        # do not allow multiple active calls to the same platform
        if self._call_active:
            return
        self._call_active = True
        result = await self._hub.async_pb_call(
            self._slave, self._verify_address, 1, self._verify_type
        )
        self._call_active = False
        if result is None:
            if self._lazy_errors:
                self._lazy_errors -= 1
                return
            self._lazy_errors = self._lazy_error_count
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._lazy_errors = self._lazy_error_count
        self._attr_available = True
        if self._verify_type in (CALL_TYPE_COIL, CALL_TYPE_DISCRETE):
            self._attr_is_on = bool(result.bits[0] & 1)
        else:
            value = int(result.registers[0])
            if value == self._state_on:
                self._attr_is_on = True
            elif value == self._state_off:
                self._attr_is_on = False
            elif value is not None:
                _LOGGER.error(
                    (
                        "Unexpected response from modbus device slave %s register %s,"
                        " got 0x%2x"
                    ),
                    self._slave,
                    self._verify_address,
                    value,
                )
        self.async_write_ha_state()
