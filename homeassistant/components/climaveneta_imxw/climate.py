"""Support for the Mitsubishi-Climaveneta iMXW fancoil series."""
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
    PLATFORM_SCHEMA,
    SWING_OFF,
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
TARGET_TEMPERATURE_SUMMER_REGISTER = 0x102D
TARGET_TEMPERATURE_WINTER_REGISTER = 0x102E

STATE_READ_ON_OFF_REGISTER = 0x100F
STATE_READ_FAN_ONLY_REGISTER = 0x1010
STATE_READ_SEASON_REGISTER = 0x1013
STATE_READ_FAN_AUTO_REGISTER = 0x1017
STATE_READ_FAN_STOP_REGISTER = 0x1018
STATE_READ_FAN_MIN_SPEED_REGISTER = 0x1019
STATE_READ_FAN_MED_SPEED_REGISTER = 0x101A
STATE_READ_FAN_MAX_SPEED_REGISTER = 0x101B
STATE_READ_EV_WATER_REGISTER = 0x101C

ACTUAL_AIR_TEMPERATURE_REGISTER = 0x1002
ACTUAL_WATER_TEMPERATURE_REGISTER = 0x1003

STATE_WRITE_ON_OFF_REGISTER = 0x105C
STATE_WRITE_MODE_REGISTER = 0x105D
STATE_WRITE_FAN_SPEED_REGISTER = 0x105E


SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ClimavenetaIMXW Platform."""
    modbus_slave = config.get(CONF_SLAVE)
    name = config.get(CONF_NAME)
    hub = get_hub(hass, config[CONF_HUB])
    async_add_entities([ClimavenetaIMXW(hub, modbus_slave, name)], True)


class ClimavenetaIMXW(ClimateEntity):
    """Representation of a ClimavenetaIMXW fancoil unit."""

    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_hvac_mode = FAN_AUTO

    _attr_hvac_mode = HVACMode.COOL
    _attr_hvac_modes = [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    ]

    _attr_swing_modes = [SWING_OFF]
    _attr_swing_mode = SWING_OFF

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
        self._summer_winter = 0
        self._target_temperature_winter: int | None = None
        self._attr_winter_temperature = 0.0
        self._attr_summer_temperature = 0.0
        self._exchanger_temperature = 0.0
        self._t1_alarm = 0
        self._t3_alarm = 0
        self._water_drain = 0
        self._min_temp = 15
        self._max_temp = 30
        self._attr_on_off = 0
        self._attr_fan_only = 0
        self._attr_ev_water = 0
        self._attr_unique_id = f"{str(hub.name)}_{name}_{str(modbus_slave)}"

    async def async_update(self) -> None:
        """Update unit attributes."""

        # setpoint and actuals
        self._summer_winter = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_READ_SEASON_REGISTER
        )

        if self._summer_winter == MODE_WINTER:  # winter
            self._attr_winter_temperature = await self._async_read_temp_from_register(
                CALL_TYPE_REGISTER_HOLDING, TARGET_TEMPERATURE_WINTER_REGISTER
            )
            self._attr_target_temperature = self._attr_winter_temperature
        else:  # summer
            self._attr_summer_temperature = await self._async_read_temp_from_register(
                CALL_TYPE_REGISTER_HOLDING, TARGET_TEMPERATURE_SUMMER_REGISTER
            )
            self._attr_target_temperature = self._attr_summer_temperature

        self._attr_current_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, ACTUAL_AIR_TEMPERATURE_REGISTER
        )

        # state heating/cooling/fan only/off
        self._attr_on_off = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_READ_ON_OFF_REGISTER
        )
        if self._attr_on_off:
            self._attr_fan_only = await self._async_read_int16_from_register(
                CALL_TYPE_REGISTER_HOLDING, STATE_READ_FAN_ONLY_REGISTER
            )
            self._attr_ev_water = await self._async_read_int16_from_register(
                CALL_TYPE_REGISTER_HOLDING, STATE_READ_EV_WATER_REGISTER
            )
            if self._attr_fan_only == MODE_ON:
                self._attr_hvac_mode = HVACMode.FAN_ONLY
                self._attr_hvac_action = HVACAction.FAN
            else:
                if self._summer_winter == MODE_SUMMER:
                    self._attr_hvac_mode = HVACMode.COOL
                    if self._attr_ev_water == WATER_CIRCULATING:
                        self._attr_hvac_action = HVACAction.COOLING
                    else:
                        self._attr_hvac_action = HVACAction.IDLE

                else:
                    self._attr_hvac_mode = HVACMode.HEAT
                    if self._attr_ev_water == WATER_CIRCULATING:
                        self._attr_hvac_action = HVACAction.HEATING
                    else:
                        self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF

        # fan speed

        fan_auto = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_READ_FAN_AUTO_REGISTER
        )
        if fan_auto == MODE_ON:
            self._attr_fan_mode = FAN_AUTO
        else:
            fan_min = await self._async_read_int16_from_register(
                CALL_TYPE_REGISTER_HOLDING, STATE_READ_FAN_MIN_SPEED_REGISTER
            )
            if fan_min == MODE_ON:
                self._attr_fan_mode = FAN_LOW
            else:
                fan_med = await self._async_read_int16_from_register(
                    CALL_TYPE_REGISTER_HOLDING, STATE_READ_FAN_MED_SPEED_REGISTER
                )
                if fan_med == MODE_ON:
                    self._attr_fan_mode = FAN_MEDIUM
                else:
                    fan_max = await self._async_read_int16_from_register(
                        CALL_TYPE_REGISTER_HOLDING,
                        STATE_READ_FAN_MAX_SPEED_REGISTER,
                    )
                    if fan_max == MODE_ON:
                        self._attr_fan_mode = FAN_HIGH
                    else:
                        self._attr_fan_mode = FAN_AUTO  # should never arrive here...

        # print something for debugging

        self._t1_alarm = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, 0x1028
        )

        self._t3_alarm = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, 0x102A
        )

        self._water_drain = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, 0x102B
        )

        #        _LOGGER.error(
        #            "Climaveneta iMXW %s. Winter: %d. ActualT: %f SetpointT_winter: %f SetpointT_summer: %f",
        #            self._attr_name,
        #            self._summer_winter,
        #            self._attr_current_temperature,
        #            self._attr_winter_temperature,
        #            self._attr_summer_temperature,
        #        )
        # _LOGGER.error(
        #    "OnOff: %d. EV_Water: %d",
        #    self._attr_on_off,
        #    self._attr_ev_water,
        # )

        #        t2_temp = await self._async_read_temp_from_register(
        #            CALL_TYPE_REGISTER_HOLDING, 0x1003
        #        )
        self._exchanger_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, 0x1004
        )

        # _LOGGER.error(
        #   "Name: %s T1: %d. T3: %d",
        #    self._attr_name,
        #    self._attr_current_temperature,
        #    self._exchanger_temperature,
        # )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "t1_alarm": self._t1_alarm,
            "t3_alarm": self._t3_alarm,
            "water_drain_alarm": self._water_drain,
            "heat_exchanger_temperature": self._exchanger_temperature,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            _LOGGER.error("Received invalid temperature")
            return

        if self._summer_winter == MODE_SUMMER:
            register = TARGET_TEMPERATURE_SUMMER_REGISTER
        else:
            register = TARGET_TEMPERATURE_WINTER_REGISTER

        if await self._async_write_int16_to_register(
            register, int(target_temperature * 10)
        ):
            self._attr_target_temperature = target_temperature
        else:
            _LOGGER.error("Modbus error setting target temperature to Climaveneta iMXW")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode in (FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH):
            if self.fan_modes and await self._async_write_int16_to_register(
                STATE_WRITE_FAN_SPEED_REGISTER, self.fan_modes.index(fan_mode)
            ):
                self._attr_fan_mode = fan_mode
            else:
                _LOGGER.error("Modbus error setting fan mode to Climaveneta iMXW")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._async_write_int16_to_register(
                STATE_WRITE_ON_OFF_REGISTER, MODE_OFF
            )
        else:
            # if the device is off, then power it on and then set the mode
            if self._attr_on_off == MODE_OFF:
                await self._async_write_int16_to_register(
                    STATE_WRITE_ON_OFF_REGISTER, MODE_ON
                )
            if self.hvac_modes and await self._async_write_int16_to_register(
                STATE_WRITE_MODE_REGISTER, self.hvac_modes.index(hvac_mode)
            ):
                self._attr_hvac_mode = hvac_mode
            else:
                _LOGGER.error("Modbus error setting fan mode to Climaveneta iMXW")

    # Based on _async_read_register in ModbusThermostat class
    async def _async_read_int16_from_register(
        self, register_type: str, register: int
    ) -> int:
        """Read register using the Modbus hub slave."""

        # _LOGGER.error(
        #     "Climaveneta iMWX read from slave %s, register %s",
        #     str(self._slave),
        #     str(register),
        # )

        result = await self._hub.async_pymodbus_call(
            self._slave, register, 1, register_type
        )
        if result is None:
            _LOGGER.error("Error reading value from Climaveneta iMXW modbus adapter")
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
