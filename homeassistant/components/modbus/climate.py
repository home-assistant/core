"""Support for Generic Modbus Thermostats."""
from __future__ import annotations

import logging
import struct
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import SUPPORT_TARGET_TEMPERATURE
from homeassistant.const import (
    CONF_COUNT,
    CONF_NAME,
    CONF_OFFSET,
    CONF_STRUCTURE,
    CONF_TEMPERATURE_UNIT,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .base_platform import BasePlatform
from .const import (
    ATTR_TEMPERATURE,
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_COILS,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_CLIMATES,
    CONF_DATA_TYPE,
    CONF_HVAC_ACTION,
    CONF_HVAC_ACTION_DATA_TYPE,
    CONF_HVAC_ACTION_SUPPORTED,
    CONF_HVAC_ACTION_TYPE,
    CONF_HVAC_MODE,
    CONF_HVAC_MODE_DATA_TYPE,
    CONF_HVAC_MODE_SUPPORTED,
    CONF_HVAC_MODE_TYPE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_STEP,
    CONF_SWAP,
    CONF_SWAP_BYTE,
    CONF_SWAP_WORD,
    CONF_SWAP_WORD_BYTE,
    CONF_TARGET_TEMP,
    DEFAULT_HVAC_ACTION,
    DEFAULT_HVAC_MODE,
    DEFAULT_STRUCT_COUNT,
    DEFAULT_STRUCT_FORMAT,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Read configuration and create Modbus climate."""
    if discovery_info is None:
        return

    entities = []
    for entity in discovery_info[CONF_CLIMATES]:
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        entities.append(ModbusThermostat(hub, entity))

    async_add_entities(entities)


class ModbusThermostat(BasePlatform, RestoreEntity, ClimateEntity):
    """Representation of a Modbus Thermostat."""

    def __init__(
        self,
        hub: ModbusHub,
        config: dict[str, Any],
    ) -> None:
        """Initialize the modbus thermostat."""
        super().__init__(hub, config)
        self._target_temperature_register = config[CONF_TARGET_TEMP]
        self._target_temperature = None
        self._current_temperature = None
        self._data_type = config[CONF_DATA_TYPE]
        self._structure = config[CONF_STRUCTURE]
        self._count = config[CONF_COUNT]
        self._precision = config[CONF_PRECISION]
        self._scale = config[CONF_SCALE]
        self._offset = config[CONF_OFFSET]
        self._unit = config[CONF_TEMPERATURE_UNIT]
        self._max_temp = config[CONF_MAX_TEMP]
        self._min_temp = config[CONF_MIN_TEMP]
        self._temp_step = config[CONF_STEP]
        self._swap = config[CONF_SWAP]
        self._hvac_action_register = config.get(CONF_HVAC_ACTION, None)
        self._hvac_action_supported = config[CONF_HVAC_ACTION_SUPPORTED]
        self._hvac_action_type = config[CONF_HVAC_ACTION_TYPE]
        self._hvac_action_data_type = config[CONF_HVAC_ACTION_DATA_TYPE]
        self._hvac_action = DEFAULT_HVAC_ACTION
        self._hvac_mode_register = config.get(CONF_HVAC_MODE, None)
        self._hvac_mode_supported = config[CONF_HVAC_MODE_SUPPORTED]
        self._hvac_mode_type = config[CONF_HVAC_MODE_TYPE]
        self._hvac_mode_data_type = config[CONF_HVAC_MODE_DATA_TYPE]
        self._hvac_mode = DEFAULT_HVAC_MODE

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.attributes.get(ATTR_TEMPERATURE):
            self._target_temperature = float(state.attributes[ATTR_TEMPERATURE])

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the possible HVAC modes."""
        return list(self._hvac_mode_supported.keys())

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if (
            hvac_mode in self._hvac_mode_supported
            and self._hvac_mode_register is not None
        ):
            dict_value = self._hvac_mode_supported[hvac_mode]
        else:
            return

        if self._hvac_mode_type == CALL_TYPE_REGISTER_HOLDING:
            as_bytes = struct.pack(
                DEFAULT_STRUCT_FORMAT[self._hvac_mode_data_type], dict_value
            )
            registers = [
                int.from_bytes(as_bytes[i : i + 2], "big")
                for i in range(0, len(as_bytes), 2)
            ]
            result = await self._hub.async_pymodbus_call(
                self._slave,
                self._hvac_mode_register,
                registers,
                CALL_TYPE_WRITE_REGISTERS,
            )
        elif self._hvac_mode_type == CALL_TYPE_COIL:
            result = await self._hub.async_pymodbus_call(
                self._slave,
                dict_value,
                1,
                CALL_TYPE_WRITE_COILS,
            )
        else:
            return

        self._available = result is not None
        await self.async_update()

    @property
    def hvac_action(self):
        """Return current HVAC action."""
        return self._hvac_action

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT if self._unit == "F" else TEMP_CELSIUS

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        return PRECISION_TENTHS if self._precision >= 1 else PRECISION_WHOLE

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._temp_step

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        target_temperature = int(
            (kwargs.get(ATTR_TEMPERATURE) - self._offset) / self._scale
        )
        byte_string = struct.pack(self._structure, target_temperature)
        struct_string = f">{DEFAULT_STRUCT_FORMAT[self._data_type]}"
        register_value = struct.unpack(struct_string, byte_string)[0]
        result = await self._hub.async_pymodbus_call(
            self._slave,
            self._target_temperature_register,
            register_value,
            CALL_TYPE_WRITE_REGISTERS,
        )
        self._available = result is not None
        await self.async_update()

    def _swap_registers(self, registers):
        """Do swap as needed."""
        if self._swap in [CONF_SWAP_BYTE, CONF_SWAP_WORD_BYTE]:
            # convert [12][34] --> [21][43]
            for i, register in enumerate(registers):
                registers[i] = int.from_bytes(
                    register.to_bytes(2, byteorder="little"),
                    byteorder="big",
                    signed=False,
                )
        if self._swap in [CONF_SWAP_WORD, CONF_SWAP_WORD_BYTE]:
            # convert [12][34] ==> [34][12]
            registers.reverse()
        return registers

    async def async_update(self, now=None):
        """Update Target & Current Temperature. Update HVAC Mode & Action."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval

        # do not allow multiple active calls to the same platform
        if self._call_active:
            return
        self._call_active = True
        self._target_temperature = await self._async_read_register(
            CALL_TYPE_REGISTER_HOLDING,
            self._target_temperature_register,
            self._count,
            self._structure,
        )
        self._current_temperature = await self._async_read_register(
            self._input_type,
            self._address,
            self._count,
            self._structure,
        )
        if self._hvac_action_register is not None:
            self._hvac_action = await self._async_update_hvac_attribute(
                self._hvac_action_type,
                self._hvac_action_register,
                self._hvac_action_data_type,
                self._hvac_action_supported,
            )
            self._hvac_action = (
                DEFAULT_HVAC_ACTION if self._hvac_action == -1 else self._hvac_action
            )
        if self._hvac_mode_register is not None:
            self._hvac_mode = await self._async_update_hvac_attribute(
                self._hvac_mode_type,
                self._hvac_mode_register,
                self._hvac_mode_data_type,
                self._hvac_mode_supported,
            )
            self._hvac_mode = (
                DEFAULT_HVAC_MODE if self._hvac_mode == -1 else self._hvac_mode
            )

        self._call_active = False
        self.async_write_ha_state()

    async def _async_read_register(
        self, register_type, register, count, structure
    ) -> float:
        """Read register using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, register, count, register_type
        )
        if result is None:
            self._available = False
            return -1

        registers = self._swap_registers(result.registers)
        byte_string = b"".join([x.to_bytes(2, byteorder="big") for x in registers])
        val = struct.unpack(structure, byte_string)
        if len(val) != 1 or not isinstance(val[0], (float, int)):
            _LOGGER.error(
                "Unable to parse result as a single int or float value; adjust your configuration. Result: %s",
                str(val),
            )
            return -1

        val2 = val[0]
        register_value = format(
            (self._scale * val2) + self._offset, f".{self._precision}f"
        )
        register_value2 = float(register_value)
        self._available = True

        return register_value2

    async def _async_read_coil(self, register_type, register) -> bool | None:
        """Read coil/discrete_input using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, register, 1, register_type
        )
        if result is None:
            self._available = False
            return None
        return bool(result.bits[0] & 1)

    async def _async_update_hvac_attribute(
        self, register_type, register, data_type, supported
    ) -> str | None:
        """Update either HVAC_ACTION or HVAC_MODE from registers/coils."""
        if (
            register_type == CALL_TYPE_REGISTER_HOLDING
            or register_type == CALL_TYPE_REGISTER_INPUT
        ):
            register_value = await self._async_read_register(
                register_type,
                register,
                DEFAULT_STRUCT_COUNT[data_type],
                DEFAULT_STRUCT_FORMAT[data_type],
            )
            for mode, value in supported.items():
                if register_value == float(value):
                    return mode
            _LOGGER.error(
                "Can't process hvac register values; adjust your configuration"
            )
            return None

        elif register_type == CALL_TYPE_DISCRETE or register_type == CALL_TYPE_COIL:
            for mode, address in supported.items():
                value = await self._async_read_coil(register_type, address)
                if value:
                    return mode
            _LOGGER.error("Can't process hvac coil values; adjust your configuration")
            return None
        else:
            _LOGGER.error(
                "Unknown type: %s; adjust your configuration", str(register_type)
            )
            return None
