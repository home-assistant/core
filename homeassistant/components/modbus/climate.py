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
    CONF_NAME,
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

from .base_platform import BaseStructPlatform
from .const import (
    ATTR_TEMPERATURE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_CLIMATES,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_STEP,
    CONF_TARGET_TEMP,
    DATA_TYPE_INT16,
    DATA_TYPE_INT32,
    DATA_TYPE_INT64,
    DATA_TYPE_UINT16,
    DATA_TYPE_UINT32,
    DATA_TYPE_UINT64,
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


class ModbusThermostat(BaseStructPlatform, RestoreEntity, ClimateEntity):
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
        self._structure = config[CONF_STRUCTURE]
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
        target_temperature = (
            float(kwargs.get(ATTR_TEMPERATURE)) - self._offset
        ) / self._scale
        if self._data_type in [
            DATA_TYPE_INT16,
            DATA_TYPE_INT32,
            DATA_TYPE_INT64,
            DATA_TYPE_UINT16,
            DATA_TYPE_UINT32,
            DATA_TYPE_UINT64,
        ]:
            target_temperature = int(target_temperature)
        as_bytes = struct.pack(self._structure, target_temperature)
        raw_regs = [
            int.from_bytes(as_bytes[i : i + 2], "big")
            for i in range(0, len(as_bytes), 2)
        ]
        registers = self._swap_registers(raw_regs)
        result = await self._hub.async_pymodbus_call(
            self._slave,
            self._target_temperature_register,
            registers,
            CALL_TYPE_WRITE_REGISTERS,
        )
        self._available = result is not None
        await self.async_update()

    async def async_update(self, now=None):
        """Update Target & Current Temperature."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval

        # do not allow multiple active calls to the same platform
        if self._call_active:
            return
        self._call_active = True
        self._target_temperature = await self._async_read_register(
            CALL_TYPE_REGISTER_HOLDING, self._target_temperature_register
        )
        self._current_temperature = await self._async_read_register(
            self._input_type, self._address
        )
        self._call_active = False
        self.async_write_ha_state()

    async def _async_read_register(self, register_type, register) -> float | None:
        """Read register using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, register, self._count, register_type
        )
        if result is None:
            self._available = False
            return -1

        self.unpack_structure_result(result.registers)

        self._available = True

        if self._value is None:
            return None
        return float(self._value)
