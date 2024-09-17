"""Support for Generic Modbus Thermostats."""

from __future__ import annotations

from datetime import datetime
import logging
import struct
from typing import Any, cast

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    FAN_ON,
    FAN_TOP,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_TEMPERATURE_UNIT,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_REGISTER,
    CALL_TYPE_WRITE_REGISTERS,
    CONF_CLIMATES,
    CONF_FAN_MODE_AUTO,
    CONF_FAN_MODE_DIFFUSE,
    CONF_FAN_MODE_FOCUS,
    CONF_FAN_MODE_HIGH,
    CONF_FAN_MODE_LOW,
    CONF_FAN_MODE_MEDIUM,
    CONF_FAN_MODE_MIDDLE,
    CONF_FAN_MODE_OFF,
    CONF_FAN_MODE_ON,
    CONF_FAN_MODE_REGISTER,
    CONF_FAN_MODE_TOP,
    CONF_FAN_MODE_VALUES,
    CONF_HVAC_MODE_AUTO,
    CONF_HVAC_MODE_COOL,
    CONF_HVAC_MODE_DRY,
    CONF_HVAC_MODE_FAN_ONLY,
    CONF_HVAC_MODE_HEAT,
    CONF_HVAC_MODE_HEAT_COOL,
    CONF_HVAC_MODE_OFF,
    CONF_HVAC_MODE_REGISTER,
    CONF_HVAC_MODE_VALUES,
    CONF_HVAC_ONOFF_REGISTER,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_STEP,
    CONF_SWING_MODE_REGISTER,
    CONF_SWING_MODE_SWING_BOTH,
    CONF_SWING_MODE_SWING_HORIZ,
    CONF_SWING_MODE_SWING_OFF,
    CONF_SWING_MODE_SWING_ON,
    CONF_SWING_MODE_SWING_VERT,
    CONF_SWING_MODE_VALUES,
    CONF_TARGET_TEMP,
    CONF_TARGET_TEMP_WRITE_REGISTERS,
    CONF_WRITE_REGISTERS,
    DataType,
)
from .entity import BaseStructPlatform
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

HVACMODE_TO_TARG_TEMP_REG_INDEX_ARRAY = {
    HVACMode.AUTO: 0,
    HVACMode.COOL: 1,
    HVACMode.DRY: 2,
    HVACMode.FAN_ONLY: 3,
    HVACMode.HEAT: 4,
    HVACMode.HEAT_COOL: 5,
    HVACMode.OFF: 6,
    None: 0,
}


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
        entities.append(ModbusThermostat(hass, hub, entity))

    async_add_entities(entities)


class ModbusThermostat(BaseStructPlatform, RestoreEntity, ClimateEntity):
    """Representation of a Modbus Thermostat."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        hass: HomeAssistant,
        hub: ModbusHub,
        config: dict[str, Any],
    ) -> None:
        """Initialize the modbus thermostat."""
        super().__init__(hass, hub, config)
        self._target_temperature_register = config[CONF_TARGET_TEMP]
        self._target_temperature_write_registers = config[
            CONF_TARGET_TEMP_WRITE_REGISTERS
        ]
        self._unit = config[CONF_TEMPERATURE_UNIT]
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_temperature_unit = (
            UnitOfTemperature.FAHRENHEIT
            if self._unit == "F"
            else UnitOfTemperature.CELSIUS
        )
        self._attr_precision = (
            PRECISION_TENTHS if self._precision >= 1 else PRECISION_WHOLE
        )
        self._attr_min_temp = config[CONF_MIN_TEMP]
        self._attr_max_temp = config[CONF_MAX_TEMP]
        self._attr_target_temperature_step = config[CONF_STEP]

        if CONF_HVAC_MODE_REGISTER in config:
            mode_config = config[CONF_HVAC_MODE_REGISTER]
            self._hvac_mode_register = mode_config[CONF_ADDRESS]
            self._attr_hvac_modes = cast(list[HVACMode], [])
            self._attr_hvac_mode = None
            self._hvac_mode_mapping: list[tuple[int, HVACMode]] = []
            self._hvac_mode_write_registers = mode_config[CONF_WRITE_REGISTERS]
            mode_value_config = mode_config[CONF_HVAC_MODE_VALUES]

            for hvac_mode_kw, hvac_mode in (
                (CONF_HVAC_MODE_OFF, HVACMode.OFF),
                (CONF_HVAC_MODE_HEAT, HVACMode.HEAT),
                (CONF_HVAC_MODE_COOL, HVACMode.COOL),
                (CONF_HVAC_MODE_HEAT_COOL, HVACMode.HEAT_COOL),
                (CONF_HVAC_MODE_AUTO, HVACMode.AUTO),
                (CONF_HVAC_MODE_DRY, HVACMode.DRY),
                (CONF_HVAC_MODE_FAN_ONLY, HVACMode.FAN_ONLY),
            ):
                if hvac_mode_kw in mode_value_config:
                    values = mode_value_config[hvac_mode_kw]
                    if not isinstance(values, list):
                        values = [values]
                    for value in values:
                        self._hvac_mode_mapping.append((value, hvac_mode))
                    self._attr_hvac_modes.append(hvac_mode)
        else:
            # No HVAC modes defined
            self._hvac_mode_register = None
            self._attr_hvac_mode = HVACMode.AUTO
            self._attr_hvac_modes = [HVACMode.AUTO]

        if CONF_FAN_MODE_REGISTER in config:
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.FAN_MODE
            )
            mode_config = config[CONF_FAN_MODE_REGISTER]
            self._fan_mode_register = mode_config[CONF_ADDRESS]
            self._attr_fan_modes = cast(list[str], [])
            self._attr_fan_mode = None
            self._fan_mode_mapping_to_modbus: dict[str, int] = {}
            self._fan_mode_mapping_from_modbus: dict[int, str] = {}
            mode_value_config = mode_config[CONF_FAN_MODE_VALUES]
            for fan_mode_kw, fan_mode in (
                (CONF_FAN_MODE_ON, FAN_ON),
                (CONF_FAN_MODE_OFF, FAN_OFF),
                (CONF_FAN_MODE_AUTO, FAN_AUTO),
                (CONF_FAN_MODE_LOW, FAN_LOW),
                (CONF_FAN_MODE_MEDIUM, FAN_MEDIUM),
                (CONF_FAN_MODE_HIGH, FAN_HIGH),
                (CONF_FAN_MODE_TOP, FAN_TOP),
                (CONF_FAN_MODE_MIDDLE, FAN_MIDDLE),
                (CONF_FAN_MODE_FOCUS, FAN_FOCUS),
                (CONF_FAN_MODE_DIFFUSE, FAN_DIFFUSE),
            ):
                if fan_mode_kw in mode_value_config:
                    value = mode_value_config[fan_mode_kw]
                    self._fan_mode_mapping_from_modbus[value] = fan_mode
                    self._fan_mode_mapping_to_modbus[fan_mode] = value
                    self._attr_fan_modes.append(fan_mode)

        else:
            # No FAN modes defined
            self._fan_mode_register = None
            self._attr_fan_mode = FAN_AUTO
            self._attr_fan_modes = [FAN_AUTO]

        # No SWING modes defined
        self._swing_mode_register = None
        if CONF_SWING_MODE_REGISTER in config:
            self._attr_supported_features = (
                self._attr_supported_features | ClimateEntityFeature.SWING_MODE
            )
            mode_config = config[CONF_SWING_MODE_REGISTER]
            self._swing_mode_register = mode_config[CONF_ADDRESS]
            self._attr_swing_modes = cast(list[str], [])
            self._attr_swing_mode = None
            self._swing_mode_modbus_mapping: list[tuple[int, str]] = []
            mode_value_config = mode_config[CONF_SWING_MODE_VALUES]
            for swing_mode_kw, swing_mode in (
                (CONF_SWING_MODE_SWING_ON, SWING_ON),
                (CONF_SWING_MODE_SWING_OFF, SWING_OFF),
                (CONF_SWING_MODE_SWING_HORIZ, SWING_HORIZONTAL),
                (CONF_SWING_MODE_SWING_VERT, SWING_VERTICAL),
                (CONF_SWING_MODE_SWING_BOTH, SWING_BOTH),
            ):
                if swing_mode_kw in mode_value_config:
                    value = mode_value_config[swing_mode_kw]
                    self._swing_mode_modbus_mapping.append((value, swing_mode))
                    self._attr_swing_modes.append(swing_mode)

        if CONF_HVAC_ONOFF_REGISTER in config:
            self._hvac_onoff_register = config[CONF_HVAC_ONOFF_REGISTER]
            self._hvac_onoff_write_registers = config[CONF_WRITE_REGISTERS]
            if HVACMode.OFF not in self._attr_hvac_modes:
                self._attr_hvac_modes.append(HVACMode.OFF)
        else:
            self._hvac_onoff_register = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.attributes.get(ATTR_TEMPERATURE):
            self._attr_target_temperature = float(state.attributes[ATTR_TEMPERATURE])

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if self._hvac_onoff_register is not None:
            # Turn HVAC Off by writing 0 to the On/Off register, or 1 otherwise.
            if self._hvac_onoff_write_registers:
                await self._hub.async_pb_call(
                    self._slave,
                    self._hvac_onoff_register,
                    [0 if hvac_mode == HVACMode.OFF else 1],
                    CALL_TYPE_WRITE_REGISTERS,
                )
            else:
                await self._hub.async_pb_call(
                    self._slave,
                    self._hvac_onoff_register,
                    0 if hvac_mode == HVACMode.OFF else 1,
                    CALL_TYPE_WRITE_REGISTER,
                )

        if self._hvac_mode_register is not None:
            # Write a value to the mode register for the desired mode.
            for value, mode in self._hvac_mode_mapping:
                if mode == hvac_mode:
                    if self._hvac_mode_write_registers:
                        await self._hub.async_pb_call(
                            self._slave,
                            self._hvac_mode_register,
                            [value],
                            CALL_TYPE_WRITE_REGISTERS,
                        )
                    else:
                        await self._hub.async_pb_call(
                            self._slave,
                            self._hvac_mode_register,
                            value,
                            CALL_TYPE_WRITE_REGISTER,
                        )
                    break

        await self.async_update()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if self._fan_mode_register is not None:
            # Write a value to the mode register for the desired mode.
            value = self._fan_mode_mapping_to_modbus[fan_mode]
            if isinstance(self._fan_mode_register, list):
                await self._hub.async_pb_call(
                    self._slave,
                    self._fan_mode_register[0],
                    [value],
                    CALL_TYPE_WRITE_REGISTERS,
                )
            else:
                await self._hub.async_pb_call(
                    self._slave,
                    self._fan_mode_register,
                    value,
                    CALL_TYPE_WRITE_REGISTER,
                )

        await self.async_update()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        if self._swing_mode_register:
            # Write a value to the mode register for the desired mode.
            for value, smode in self._swing_mode_modbus_mapping:
                if swing_mode == smode:
                    if isinstance(self._swing_mode_register, list):
                        await self._hub.async_pb_call(
                            self._slave,
                            self._swing_mode_register[0],
                            [value],
                            CALL_TYPE_WRITE_REGISTERS,
                        )
                    else:
                        await self._hub.async_pb_call(
                            self._slave,
                            self._swing_mode_register,
                            value,
                            CALL_TYPE_WRITE_REGISTER,
                        )
                    break
        await self.async_update()

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
        registers = self._swap_registers(raw_regs, 0)

        if self._data_type in (
            DataType.INT16,
            DataType.UINT16,
        ):
            if self._target_temperature_write_registers:
                result = await self._hub.async_pb_call(
                    self._slave,
                    self._target_temperature_register[
                        HVACMODE_TO_TARG_TEMP_REG_INDEX_ARRAY[self._attr_hvac_mode]
                    ],
                    [int(float(registers[0]))],
                    CALL_TYPE_WRITE_REGISTERS,
                )
            else:
                result = await self._hub.async_pb_call(
                    self._slave,
                    self._target_temperature_register[
                        HVACMODE_TO_TARG_TEMP_REG_INDEX_ARRAY[self._attr_hvac_mode]
                    ],
                    int(float(registers[0])),
                    CALL_TYPE_WRITE_REGISTER,
                )
        else:
            result = await self._hub.async_pb_call(
                self._slave,
                self._target_temperature_register[
                    HVACMODE_TO_TARG_TEMP_REG_INDEX_ARRAY[self._attr_hvac_mode]
                ],
                [int(float(i)) for i in registers],
                CALL_TYPE_WRITE_REGISTERS,
            )
        self._attr_available = result is not None
        await self.async_update()

    async def async_update(self, now: datetime | None = None) -> None:
        """Update Target & Current Temperature."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval

        self._attr_target_temperature = await self._async_read_register(
            CALL_TYPE_REGISTER_HOLDING,
            self._target_temperature_register[
                HVACMODE_TO_TARG_TEMP_REG_INDEX_ARRAY[self._attr_hvac_mode]
            ],
        )

        self._attr_current_temperature = await self._async_read_register(
            self._input_type, self._address
        )
        # Read the HVAC mode register if defined
        if self._hvac_mode_register is not None:
            hvac_mode = await self._async_read_register(
                CALL_TYPE_REGISTER_HOLDING, self._hvac_mode_register, raw=True
            )

            # Translate the value received
            if hvac_mode is not None:
                self._attr_hvac_mode = None
                for value, mode in self._hvac_mode_mapping:
                    if hvac_mode == value:
                        self._attr_hvac_mode = mode
                        break

        # Read the Fan mode register if defined
        if self._fan_mode_register is not None:
            fan_mode = await self._async_read_register(
                CALL_TYPE_REGISTER_HOLDING,
                self._fan_mode_register
                if isinstance(self._fan_mode_register, int)
                else self._fan_mode_register[0],
                raw=True,
            )

            # Translate the value received
            if fan_mode is not None:
                self._attr_fan_mode = self._fan_mode_mapping_from_modbus.get(
                    int(fan_mode), self._attr_fan_mode
                )

        # Read the Swing mode register if defined
        if self._swing_mode_register:
            swing_mode = await self._async_read_register(
                CALL_TYPE_REGISTER_HOLDING,
                self._swing_mode_register
                if isinstance(self._swing_mode_register, int)
                else self._swing_mode_register[0],
                raw=True,
            )

            self._attr_swing_mode = STATE_UNKNOWN
            for value, smode in self._swing_mode_modbus_mapping:
                if swing_mode == value:
                    self._attr_swing_mode = smode
                    break

            if self._attr_swing_mode is STATE_UNKNOWN:
                _err = f"{self.name}: No answer received from Swing mode register. State is Unknown"
                _LOGGER.error(_err)

        # Read the on/off register if defined. If the value in this
        # register is "OFF", it will take precedence over the value
        # in the mode register.
        if self._hvac_onoff_register is not None:
            onoff = await self._async_read_register(
                CALL_TYPE_REGISTER_HOLDING, self._hvac_onoff_register, raw=True
            )
            if onoff == 0:
                self._attr_hvac_mode = HVACMode.OFF

        self.async_write_ha_state()

    async def _async_read_register(
        self, register_type: str, register: int, raw: bool | None = False
    ) -> float | None:
        """Read register using the Modbus hub slave."""
        result = await self._hub.async_pb_call(
            self._slave, register, self._count, register_type
        )
        if result is None:
            self._attr_available = False
            return -1

        if raw:
            # Return the raw value read from the register, do not change
            # the object's state
            self._attr_available = True
            return int(result.registers[0])

        # The regular handling of the value
        self._value = self.unpack_structure_result(result.registers)
        if not self._value:
            self._attr_available = False
            return None
        self._attr_available = True
        return float(self._value)
