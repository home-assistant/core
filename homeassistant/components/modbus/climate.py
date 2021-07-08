"""Support for Generic Modbus Thermostats."""
from __future__ import annotations

import logging
import struct
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    CONF_COUNT,
    CONF_NAME,
    CONF_OFFSET,
    CONF_STRUCTURE,
    CONF_TEMPERATURE_UNIT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .base_platform import BasePlatform
from .const import (
    ATTR_TEMPERATURE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_CLIMATES,
    CONF_DATA_TYPE,
    CONF_HVAC_ACTION,
    CONF_HVAC_ACTION_SUPPORTED,
    CONF_HVAC_ACTION_VALUES,
    CONF_HVAC_MODE,
    CONF_HVAC_MODE_SUPPORTED,
    CONF_HVAC_MODE_VALUES,
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
        self._hvac_action_register = config[CONF_HVAC_ACTION]
        self._hvac_mode_register = config[CONF_HVAC_MODE]
        self._target_temperature = None
        self._current_temperature = None
        self._hvac_action = CURRENT_HVAC_IDLE
        self._hvac_mode = HVAC_MODE_AUTO
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

        self._init_hvac_actions(config)
        self._init_hvac_modes(config)

    def _init_hvac_actions(self, config):
        self._hvac_action_supported = config[CONF_HVAC_ACTION_SUPPORTED]
        self._hvac_action_dict = {}
        if len(config[CONF_HVAC_ACTION_SUPPORTED]) == len(
            config[CONF_HVAC_ACTION_VALUES]
        ):
            for i in range(0, len(config[CONF_HVAC_ACTION_SUPPORTED])):
                self._hvac_action_dict[config[CONF_HVAC_ACTION_SUPPORTED][i]] = config[
                    CONF_HVAC_ACTION_VALUES
                ][i]
        else:
            _LOGGER.error(
                "Unable to parse hvac actions; Length of actions list and value list are unequal; Result: %s : %s",
                str(len(config[CONF_HVAC_ACTION_SUPPORTED])),
                str(len(config[CONF_HVAC_ACTION_VALUES])),
            )
            self._available = False

    def _init_hvac_modes(self, config):
        self._hvac_mode_supported = config[CONF_HVAC_MODE_SUPPORTED]
        self._hvac_mode_dict = {}
        if len(config[CONF_HVAC_MODE_SUPPORTED]) == len(config[CONF_HVAC_MODE_VALUES]):
            for i in range(0, len(config[CONF_HVAC_MODE_SUPPORTED])):
                self._hvac_mode_dict[config[CONF_HVAC_MODE_SUPPORTED][i]] = config[
                    CONF_HVAC_MODE_VALUES
                ][i]
        else:
            _LOGGER.error(
                "Unable to parse hvac modes; Length of mode list and value list are unequal; Result: %s : %s",
                str(len(config[CONF_HVAC_MODE_SUPPORTED])),
                str(len(config[CONF_HVAC_MODE_VALUES])),
            )
            self._available = False

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
        return self._hvac_mode_supported

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode in self._hvac_mode_dict and self._hvac_mode_register != 0:
            mode_value = self._hvac_mode_dict[hvac_mode]
            result = await self._hub.async_pymodbus_call(
                self._slave,
                self._hvac_mode_register,
                mode_value,
                CALL_TYPE_WRITE_REGISTERS,
            )
            self._available = result is not None
            await self.async_update()
        else:
            return

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

        # value needs to be cast back to unint16_t for pymodbus
        byte_string = struct.pack(self._structure, target_temperature)
        register_value = struct.unpack(">2h", byte_string)

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

    def _parse_hvac_mode(self, value):
        """Parse hvac mode from register value."""
        if len(self._hvac_mode_dict) >= 1:
            for dict_key, dict_value in self._hvac_mode_dict.items():
                if dict_value == value:
                    return dict_key
        _LOGGER.error(
            "Unable to parse hvac mode value; adjust your configuration. Result: %s",
            str(value),
        )
        return HVAC_MODE_AUTO

    def _parse_hvac_action(self, value):
        """Parse hvac action from register value."""
        if len(self._hvac_action_dict) >= 1:
            for dict_key, dict_value in self._hvac_action_dict.items():
                if dict_value == value:
                    return dict_key
        _LOGGER.error(
            "Unable to parse hvac action value; adjust your configuration. Result: %s",
            str(value),
        )
        return CURRENT_HVAC_IDLE

    async def async_update(self, now=None):
        """Update Target & Current Temperature. Update HVAC Mode & Action."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        self._target_temperature = await self._async_read_register(
            self._input_type,
            self._target_temperature_register,
            self._count,
            self._structure,
        )
        self._current_temperature = await self._async_read_register(
            self._input_type, self._address, self._count, self._structure
        )
        if self._hvac_mode_register != 0:
            hvac_mode = await self._async_read_register(
                CALL_TYPE_REGISTER_HOLDING, self._hvac_mode_register, 1, ">h"
            )
            self._hvac_mode = self._parse_hvac_mode(hvac_mode)
        if self._hvac_action_register != 0:
            hvac_action = await self._async_read_register(
                CALL_TYPE_REGISTER_HOLDING, self._hvac_action_register, 1, ">h"
            )
            self._hvac_action = self._parse_hvac_action(hvac_action)

        self.async_write_ha_state()

    async def _async_read_register(
        self, register_type, register, count, structure
    ) -> float | None:
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
