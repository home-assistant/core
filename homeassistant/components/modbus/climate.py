"""Support for Generic Modbus Thermostats."""
from __future__ import annotations

import logging
import struct
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    CONF_ADDRESS,
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
    CONF_CURRENT_TEMP,
    CONF_CURRENT_TEMP_REGISTER_TYPE,
    CONF_DATA_COUNT,
    CONF_DATA_TYPE,
    CONF_INPUT_TYPE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_STEP,
    CONF_TARGET_TEMP,
    DATA_TYPE_CUSTOM,
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
        count = entity[CONF_DATA_COUNT]
        data_type = entity[CONF_DATA_TYPE]
        name = entity[CONF_NAME]
        structure = entity[CONF_STRUCTURE]

        if data_type != DATA_TYPE_CUSTOM:
            try:
                structure = f">{DEFAULT_STRUCT_FORMAT[data_type][count]}"
            except KeyError:
                _LOGGER.error(
                    "Climate %s: Unable to find a data type matching count value %s, try a custom type",
                    name,
                    count,
                )
                continue

        try:
            size = struct.calcsize(structure)
        except struct.error as err:
            _LOGGER.error("Error in sensor %s structure: %s", name, err)
            continue

        if count * 2 != size:
            _LOGGER.error(
                "Structure size (%d bytes) mismatch registers count (%d words)",
                size,
                count,
            )
            continue

        entity[CONF_STRUCTURE] = structure
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
        config[CONF_ADDRESS] = "0"
        config[CONF_INPUT_TYPE] = ""
        super().__init__(hub, config)
        self._target_temperature_register = config[CONF_TARGET_TEMP]
        self._current_temperature_register = config[CONF_CURRENT_TEMP]
        self._current_temperature_register_type = config[
            CONF_CURRENT_TEMP_REGISTER_TYPE
        ]
        self._target_temperature = None
        self._current_temperature = None
        self._data_type = config[CONF_DATA_TYPE]
        self._structure = config[CONF_STRUCTURE]
        self._count = config[CONF_DATA_COUNT]
        self._precision = config[CONF_PRECISION]
        self._scale = config[CONF_SCALE]
        self._offset = config[CONF_OFFSET]
        self._unit = config[CONF_TEMPERATURE_UNIT]
        self._max_temp = config[CONF_MAX_TEMP]
        self._min_temp = config[CONF_MIN_TEMP]
        self._temp_step = config[CONF_STEP]

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
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the possible HVAC modes."""
        return [HVAC_MODE_AUTO]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        # Home Assistant expects this method.
        # We'll keep it here to avoid getting exceptions.

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
        byte_string = struct.pack(self._structure, target_temperature)
        register_value = struct.unpack(">h", byte_string[0:2])[0]
        result = await self._hub.async_pymodbus_call(
            self._slave,
            self._target_temperature_register,
            register_value,
            CALL_TYPE_WRITE_REGISTERS,
        )
        self._available = result is not None
        await self.async_update()

    async def async_update(self, now=None):
        """Update Target & Current Temperature."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        self._target_temperature = await self._async_read_register(
            CALL_TYPE_REGISTER_HOLDING, self._target_temperature_register
        )
        self._current_temperature = await self._async_read_register(
            self._current_temperature_register_type, self._current_temperature_register
        )

        self.async_write_ha_state()

    async def _async_read_register(self, register_type, register) -> float | None:
        """Read register using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, register, self._count, register_type
        )
        if result is None:
            self._available = False
            return -1

        byte_string = b"".join(
            [x.to_bytes(2, byteorder="big") for x in result.registers]
        )
        val = struct.unpack(self._structure, byte_string)
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
