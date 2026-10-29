"""Support for Generic Modbus Water Heaters."""

import struct
from typing import Any, override

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_TEMPERATURE_UNIT,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_CURRENT_TEMP_OFFSET,
    CONF_CURRENT_TEMP_SCALE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_OFF_VALUE,
    CONF_ON_VALUE,
    CONF_ONOFF_COIL,
    CONF_ONOFF_REGISTER,
    CONF_OPERATION_MODE_ECO,
    CONF_OPERATION_MODE_ELECTRIC,
    CONF_OPERATION_MODE_GAS,
    CONF_OPERATION_MODE_HEAT_PUMP,
    CONF_OPERATION_MODE_HIGH_DEMAND,
    CONF_OPERATION_MODE_OFF,
    CONF_OPERATION_MODE_PERFORMANCE,
    CONF_OPERATION_MODE_REGISTER,
    CONF_OPERATION_MODE_VALUES,
    CONF_STEP,
    CONF_TARGET_TEMP,
    CONF_TARGET_TEMP_OFFSET,
    CONF_TARGET_TEMP_SCALE,
    CONF_TARGET_TEMP_WRITE_REGISTERS,
    CONF_WATER_HEATERS,
    CONF_WRITE_REGISTERS,
)
from .entity import ModbusStructEntity
from .modbus import ModbusHub

PARALLEL_UPDATES = 1

OPERATION_MODES = (
    (CONF_OPERATION_MODE_OFF, STATE_OFF),
    (CONF_OPERATION_MODE_ECO, STATE_ECO),
    (CONF_OPERATION_MODE_ELECTRIC, STATE_ELECTRIC),
    (CONF_OPERATION_MODE_PERFORMANCE, STATE_PERFORMANCE),
    (CONF_OPERATION_MODE_HIGH_DEMAND, STATE_HIGH_DEMAND),
    (CONF_OPERATION_MODE_HEAT_PUMP, STATE_HEAT_PUMP),
    (CONF_OPERATION_MODE_GAS, STATE_GAS),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus water heaters."""
    if discovery_info is None or not (
        water_heaters := discovery_info[CONF_WATER_HEATERS]
    ):
        return
    hub = get_hub(hass, discovery_info[CONF_NAME])
    async_add_entities(ModbusWaterHeater(hass, hub, config) for config in water_heaters)


class ModbusWaterHeater(ModbusStructEntity, WaterHeaterEntity):
    """Representation of a Modbus water heater."""

    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self,
        hass: HomeAssistant,
        hub: ModbusHub,
        config: dict[str, Any],
    ) -> None:
        """Initialize the modbus water heater."""
        super().__init__(hass, hub, config)
        self._target_temperature_register: int = config[CONF_TARGET_TEMP]
        self._target_temperature_write_registers: bool = config[
            CONF_TARGET_TEMP_WRITE_REGISTERS
        ]
        self._attr_native_temperature_unit = (
            UnitOfTemperature.FAHRENHEIT
            if config[CONF_TEMPERATURE_UNIT] == "F"
            else UnitOfTemperature.CELSIUS
        )
        self._attr_precision = (
            PRECISION_TENTHS if self._precision >= 1 else PRECISION_WHOLE
        )
        self._attr_min_temp = config[CONF_MIN_TEMP]
        self._attr_max_temp = config[CONF_MAX_TEMP]
        self._attr_target_temperature_step = config[CONF_STEP]
        self._current_temp_scale: float = config[CONF_CURRENT_TEMP_SCALE]
        self._current_temp_offset: float = config[CONF_CURRENT_TEMP_OFFSET]
        self._target_temp_scale: float = config[CONF_TARGET_TEMP_SCALE]
        self._target_temp_offset: float = config[CONF_TARGET_TEMP_OFFSET]

        self._operation_mode_register: int | None = None
        self._operation_mode_write_registers = False
        self._operation_mode_from_modbus: dict[int, str] = {}
        self._operation_mode_to_modbus: dict[str, int] = {}
        if CONF_OPERATION_MODE_REGISTER in config:
            self._setup_operation_modes(config[CONF_OPERATION_MODE_REGISTER])

        self._onoff_register: int | None = config.get(CONF_ONOFF_REGISTER)
        self._onoff_coil: int | None = config.get(CONF_ONOFF_COIL)
        self._onoff_write_registers: bool = config[CONF_WRITE_REGISTERS]
        self._on_value: int = config[CONF_ON_VALUE]
        self._off_value: int = config[CONF_OFF_VALUE]
        if self._onoff_register is not None or self._onoff_coil is not None:
            self._attr_supported_features |= WaterHeaterEntityFeature.ON_OFF
            if (
                self._attr_operation_list is not None
                and STATE_OFF not in self._attr_operation_list
            ):
                self._attr_operation_list.append(STATE_OFF)

        if self._attr_operation_list:
            self._attr_supported_features |= WaterHeaterEntityFeature.OPERATION_MODE

    def _setup_operation_modes(self, mode_config: dict[str, Any]) -> None:
        """Build the operation mode mapping from the operation mode register config."""
        self._operation_mode_register = mode_config[CONF_ADDRESS]
        self._operation_mode_write_registers = mode_config[CONF_WRITE_REGISTERS]
        self._attr_operation_list = []
        for mode_kw, mode in OPERATION_MODES:
            if mode_kw not in mode_config[CONF_OPERATION_MODE_VALUES]:
                continue
            values = mode_config[CONF_OPERATION_MODE_VALUES][mode_kw]
            if not isinstance(values, list):
                values = [values]
            # the first value is the one written when the mode is selected
            self._operation_mode_to_modbus[mode] = values[0]
            for value in values:
                self._operation_mode_from_modbus[value] = mode
            self._attr_operation_list.append(mode)

    @override
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temperature = (
            float(kwargs[ATTR_TEMPERATURE]) - self._target_temp_offset
        ) / self._target_temp_scale
        if self._value_is_int:
            target_temperature = round(target_temperature)
        as_bytes = struct.pack(self._structure, target_temperature)
        registers = self._swap_registers(
            [
                int.from_bytes(as_bytes[i : i + 2], "big")
                for i in range(0, len(as_bytes), 2)
            ],
            0,
        )
        if len(registers) == 1 and not self._target_temperature_write_registers:
            result = await self._hub.async_pb_call(
                self._device_address,
                self._target_temperature_register,
                registers[0],
                CALL_TYPE_WRITE_REGISTER,
            )
        else:
            result = await self._hub.async_pb_call(
                self._device_address,
                self._target_temperature_register,
                registers,
                CALL_TYPE_WRITE_REGISTERS,
            )
        self._attr_available = result is not None
        await self.async_local_update(cancel_pending_update=True)

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        await self._async_write_onoff(operation_mode != STATE_OFF)
        if (
            self._operation_mode_register is not None
            and (value := self._operation_mode_to_modbus.get(operation_mode))
            is not None
        ):
            await self._async_write_register(
                self._operation_mode_register,
                value,
                self._operation_mode_write_registers,
            )
        await self.async_local_update(cancel_pending_update=True)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        await self._async_write_onoff(True)
        await self.async_local_update(cancel_pending_update=True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        await self._async_write_onoff(False)
        await self.async_local_update(cancel_pending_update=True)

    async def _async_write_onoff(self, turn_on: bool) -> None:
        """Write the on/off state, if an on/off coil or register is configured."""
        if self._onoff_coil is not None:
            await self._hub.async_pb_call(
                self._device_address,
                self._onoff_coil,
                1 if turn_on else 0,
                CALL_TYPE_WRITE_COIL,
            )
        elif self._onoff_register is not None:
            await self._async_write_register(
                self._onoff_register,
                self._on_value if turn_on else self._off_value,
                self._onoff_write_registers,
            )

    async def _async_write_register(
        self, address: int, value: int, write_registers: bool
    ) -> None:
        """Write a single register value."""
        if write_registers:
            await self._hub.async_pb_call(
                self._device_address, address, [value], CALL_TYPE_WRITE_REGISTERS
            )
        else:
            await self._hub.async_pb_call(
                self._device_address, address, value, CALL_TYPE_WRITE_REGISTER
            )

    @override
    async def _async_update(self) -> None:
        """Update the state of the water heater."""
        self._attr_available = True
        self._attr_native_target_temperature = await self._async_read_temperature(
            CALL_TYPE_REGISTER_HOLDING,
            self._target_temperature_register,
            self._target_temp_scale,
            self._target_temp_offset,
        )
        self._attr_native_current_temperature = await self._async_read_temperature(
            self._input_type,
            self._address,
            self._current_temp_scale,
            self._current_temp_offset,
        )

        if self._operation_mode_register is not None:
            result = await self._hub.async_pb_call(
                self._device_address,
                self._operation_mode_register,
                1,
                CALL_TYPE_REGISTER_HOLDING,
            )
            if result is None:
                self._attr_available = False
                return
            self._attr_current_operation = self._operation_mode_from_modbus.get(
                int(result.registers[0])
            )

        if self._onoff_coil is not None:
            result = await self._hub.async_pb_call(
                self._device_address, self._onoff_coil, 1, CALL_TYPE_COIL
            )
            if result is None:
                self._attr_available = False
                return
            is_on = bool(result.bits[0])
        elif self._onoff_register is not None:
            result = await self._hub.async_pb_call(
                self._device_address,
                self._onoff_register,
                1,
                CALL_TYPE_REGISTER_HOLDING,
            )
            if result is None:
                self._attr_available = False
                return
            is_on = int(result.registers[0]) != self._off_value
        else:
            return

        if not is_on:
            self._attr_current_operation = STATE_OFF
        elif self._operation_mode_register is None:
            self._attr_current_operation = STATE_ON

    async def _async_read_temperature(
        self, register_type: str, address: int, scale: float, offset: float
    ) -> float | None:
        """Read a temperature register and apply scale and offset."""
        result = await self._hub.async_pb_call(
            self._device_address, address, self._count, register_type
        )
        if result is None:
            self._attr_available = False
            return None
        value = self.unpack_structure_result(result.registers, scale, offset)
        return None if value is None else float(value)
