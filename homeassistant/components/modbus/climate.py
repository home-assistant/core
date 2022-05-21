"""Support for Generic Modbus Thermostats."""
from __future__ import annotations

from datetime import datetime
import struct
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_TEMPERATURE_UNIT,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .base_platform import BaseStructPlatform
from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_CLIMATES,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_STEP,
    CONF_TARGET_TEMP,
    DataType,
)
from .modbus import ModbusHub

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus climate."""
    if discovery_info is None:
        return

    entities = []
    for entity in discovery_info[CONF_CLIMATES]:
        hub: ModbusHub = get_hub(hass, discovery_info[CONF_NAME])
        entities.append(ModbusThermostat(hub, entity))

    async_add_entities(entities)


class ModbusThermostat(BaseStructPlatform, RestoreEntity, ClimateEntity):
    """Representation of a Modbus Thermostat."""

    _attr_hvac_mode = HVACMode.AUTO
    _attr_hvac_modes = [HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self,
        hub: ModbusHub,
        config: dict[str, Any],
    ) -> None:
        """Initialize the modbus thermostat."""
        super().__init__(hub, config)
        self._target_temperature_register = config[CONF_TARGET_TEMP]
        self._unit = config[CONF_TEMPERATURE_UNIT]

        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_temperature_unit = (
            TEMP_FAHRENHEIT if self._unit == "F" else TEMP_CELSIUS
        )
        self._attr_precision = (
            PRECISION_TENTHS if self._precision >= 1 else PRECISION_WHOLE
        )
        self._attr_min_temp = config[CONF_MIN_TEMP]
        self._attr_max_temp = config[CONF_MAX_TEMP]
        self._attr_target_temperature_step = config[CONF_TARGET_TEMP]
        self._attr_target_temperature_step = config[CONF_STEP]

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.attributes.get(ATTR_TEMPERATURE):
            self._attr_target_temperature = float(state.attributes[ATTR_TEMPERATURE])

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # Home Assistant expects this method.
        # We'll keep it here to avoid getting exceptions.

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = (
            float(kwargs[ATTR_TEMPERATURE]) - self._offset
        ) / self._scale
        if self._data_type in (
            DataType.INT16,
            DataType.INT32,
            DataType.INT64,
            DataType.UINT16,
            DataType.UINT32,
            DataType.UINT64,
        ):
            target_temperature = int(target_temperature)
        as_bytes = struct.pack(self._structure, target_temperature)
        raw_regs = [
            int.from_bytes(as_bytes[i : i + 2], "big")
            for i in range(0, len(as_bytes), 2)
        ]
        registers = self._swap_registers(raw_regs)

        if self._data_type in (
            DataType.INT16,
            DataType.UINT16,
        ):
            result = await self._hub.async_pymodbus_call(
                self._slave,
                self._target_temperature_register,
                int(float(registers[0])),
                CALL_TYPE_WRITE_REGISTER,
            )
        else:
            result = await self._hub.async_pymodbus_call(
                self._slave,
                self._target_temperature_register,
                [int(float(i)) for i in registers],
                CALL_TYPE_WRITE_REGISTERS,
            )
        self._attr_available = result is not None
        await self.async_update()

    async def async_update(self, now: datetime | None = None) -> None:
        """Update Target & Current Temperature."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval

        # do not allow multiple active calls to the same platform
        if self._call_active:
            return
        self._call_active = True
        self._attr_target_temperature = await self._async_read_register(
            CALL_TYPE_REGISTER_HOLDING, self._target_temperature_register
        )
        self._attr_current_temperature = await self._async_read_register(
            self._input_type, self._address
        )
        self._call_active = False
        self.async_write_ha_state()

    async def _async_read_register(
        self, register_type: str, register: int
    ) -> float | None:
        """Read register using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, register, self._count, register_type
        )
        if result is None:
            if self._lazy_errors:
                self._lazy_errors -= 1
                return -1
            self._lazy_errors = self._lazy_error_count
            self._attr_available = False
            return -1

        self._lazy_errors = self._lazy_error_count
        self._value = self.unpack_structure_result(result.registers)
        if not self._value:
            self._attr_available = False
            return None
        self._attr_available = True
        return float(self._value)
