"""Support for the Mitsubishi-Climaveneta iLife2 fancoil series."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.modbus import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_WRITE_REGISTER,
    CONF_HUB,
    DEFAULT_HUB,
    ModbusHub,
    get_hub,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_SLAVE,
    DEVICE_DEFAULT_NAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_SLAVE): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
    }
)


_LOGGER = logging.getLogger(__name__)


MODE_SUMMER = 0
MODE_WINTER = 1

MODE_OFF = 0
MODE_ON = 1

WATER_BYPASS = 0
WATER_CIRCULATING = 1


# registers
TARGET_TEMPERATURE_REGISTER = 231
ACTUAL_AIR_TEMPERATURE_REGISTER = 0
ACTUAL_WATER_TEMPERATURE_REGISTER = 1
STATE_READ_SETPOINT_REGISTER = 8
STATE_READ_REGISTER = 104
STATE_READ_FAN_SPEED = 15
STATE_READ_PROGRAM_REGISTER = 201
STATE_OUT_REGISTER = 9
STATE_MAN_REGISTER = 233


SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ClimavenetaILIFE Platform."""
    modbus_slave = config.get(CONF_SLAVE)
    name = config.get(CONF_NAME)
    hub = get_hub(hass, config[CONF_HUB])
    async_add_entities([ClimavenetaILIFE(hub, modbus_slave, name)], True)


class ClimavenetaILIFE(ClimateEntity):
    """Representation of a ClimavenetaILIFE fancoil unit."""

    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_hvac_mode = FAN_AUTO

    _attr_hvac_mode = HVACMode.COOL
    _attr_hvac_modes = [
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    ]

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self, hub: ModbusHub, modbus_slave: int | None, name: str | None
    ) -> None:
        """Initialize the unit."""
        self._hub = hub
        self._attr_name = name
        self._slave = modbus_slave
        self._attr_fan_mode = None
        self._filter_alarm: int | None = None
        self._heat_recovery: int | None = None
        self._heater_enabled: int | None = None
        self._heating: int | None = None
        self._cooling: int | None = None
        self._alarm = False
        self._min_temp = 15
        self._max_temp = 30
        self._attr_on_off = 0
        self._attr_fan_only = 0
        self._attr_ev_water = 0
        self._attr_unique_id = f"{str(hub.name)}_{name}_{str(modbus_slave)}"

    async def async_update(self) -> None:
        """Update unit attributes."""

        # setpoint and actuals
        self._attr_target_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_READ_SETPOINT_REGISTER
        )

        self._attr_current_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, ACTUAL_AIR_TEMPERATURE_REGISTER
        )

        # state heating/cooling/fan only/off

        man_register = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_MAN_REGISTER
        )

        program_register = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_READ_PROGRAM_REGISTER
        )
        if (program_register & (1 << 7)) == 0b10000000:
            self._attr_on_off = 0  # standby
        else:
            self._attr_on_off = 1  # normal operation

        if self._attr_on_off:
            stat_register = await self._async_read_int16_from_register(
                CALL_TYPE_REGISTER_HOLDING, STATE_READ_REGISTER
            )
            await self._async_read_int16_from_register(
                CALL_TYPE_REGISTER_HOLDING, STATE_OUT_REGISTER
            )

            if man_register == 0:
                self._attr_hvac_mode = HVACMode.HEAT_COOL
            elif man_register == 3:
                self._attr_hvac_mode = HVACMode.HEAT
            elif man_register == 5:
                self._attr_hvac_mode = HVACMode.COOL
            else:
                self._attr_hvac_mode = (
                    HVACMode.OFF
                )  # not a valid number, this register should always be 0, 3 or 5.

            if (stat_register & (1 << 1) == 0) and (stat_register & (1 << 0) == 0):
                self._attr_hvac_action = HVACAction.IDLE
            elif stat_register & (1 << 1) == 0:
                self._attr_hvac_action = HVACAction.COOLING
            else:
                self._attr_hvac_action = HVACAction.HEATING

            # fan speed
            if (program_register & 0b111) == 0b000:
                self._attr_fan_mode = FAN_AUTO
            elif (program_register & 0b111) == 0b001:
                self._attr_fan_mode = FAN_LOW
            elif (program_register & 0b111) == 0b010:
                self._attr_fan_mode = FAN_MEDIUM
            elif (program_register & 0b111) == 0b011:
                self._attr_fan_mode = FAN_HIGH
            else:
                self._attr_fan_mode = FAN_OFF  # unknown state
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
            self._attr_fan_mode = FAN_OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            _LOGGER.error("Received invalid temperature")
            return

        if await self._async_write_int16_to_register(
            TARGET_TEMPERATURE_REGISTER, int(target_temperature * 10)
        ):
            self._attr_target_temperature = target_temperature
        else:
            _LOGGER.error(
                "Modbus error setting target temperature to Climaveneta i-Life"
            )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode in (FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH) and self.fan_modes:
            fan_mode_index = self.fan_modes.index(fan_mode)

            if self._attr_on_off == MODE_OFF:
                fan_mode_index = fan_mode_index + (
                    1 << 7
                )  # keep it powered off (standby) if fan mode is set when off.

            if self.fan_modes and await self._async_write_int16_to_register(
                STATE_READ_PROGRAM_REGISTER, fan_mode_index
            ):
                self._attr_fan_mode = fan_mode
            else:
                _LOGGER.error("Modbus error setting fan mode to Climaveneta i-Life")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            if await self._async_write_int16_to_register(
                STATE_READ_PROGRAM_REGISTER, 0b10000000
            ):
                self._attr_hvac_mode = hvac_mode
            else:
                _LOGGER.error(
                    "Modbus error writing hvac mode OFF to Climaveneta i-Life"
                )
        else:
            # if the device is off, then power it on and then set the mode
            if self._attr_on_off == MODE_OFF:
                await self._async_write_int16_to_register(
                    STATE_READ_PROGRAM_REGISTER, 0
                )
            if hvac_mode == HVACMode.COOL:
                winter_summer = 5  # summer
            elif hvac_mode == HVACMode.HEAT_COOL:
                winter_summer = 0  # auto
            else:
                winter_summer = 3  # winter
            if self.hvac_modes and await self._async_write_int16_to_register(
                STATE_MAN_REGISTER, winter_summer
            ):
                self._attr_hvac_mode = hvac_mode
            else:
                _LOGGER.error(
                    "Modbus error setting hvac mode %s to Climaveneta i-Life", hvac_mode
                )

    # Based on _async_read_register in ModbusThermostat class
    async def _async_read_int16_from_register(
        self, register_type: str, register: int
    ) -> int:
        """Read register using the Modbus hub slave."""

        result = await self._hub.async_pymodbus_call(
            self._slave, register, 1, register_type
        )
        if result is None:
            _LOGGER.error("Error reading value from Climaveneta i-Life modbus adapter")
            return -1

        return int(result.registers[0])

    async def _async_read_temp_from_register(
        self, register_type: str, register: int
    ) -> float:
        result = float(
            await self._async_read_int16_from_register(register_type, register)
        )
        if not result:
            return -1
        return result / 10.0

    async def _async_write_int16_to_register(self, register: int, value: int) -> bool:
        result = await self._hub.async_pymodbus_call(
            self._slave, register, value, CALL_TYPE_WRITE_REGISTER
        )
        if not result:
            return False
        return True
