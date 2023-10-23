"""Coordinator for the climaveneta_imxw AC."""

import logging

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACAction,
    HVACMode,
)
from homeassistant.components.modbus import CALL_TYPE_REGISTER_HOLDING, ModbusHub
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ACTUAL_AIR_TEMPERATURE_REGISTER,
    ACTUAL_WATER_TEMPERATURE_REGISTER,
    ALARM_T1_REGISTER,
    ALARM_T3_REGISTER,
    ALARM_WATER_DRAIN_REGISTER,
    MODE_ON,
    MODE_SUMMER,
    MODE_WINTER,
    SCAN_INTERVAL,
    STATE_READ_EV_WATER_REGISTER,
    STATE_READ_FAN_AUTO_REGISTER,
    STATE_READ_FAN_MAX_SPEED_REGISTER,
    STATE_READ_FAN_MED_SPEED_REGISTER,
    STATE_READ_FAN_MIN_SPEED_REGISTER,
    STATE_READ_FAN_ONLY_REGISTER,
    STATE_READ_ON_OFF_REGISTER,
    STATE_READ_SEASON_REGISTER,
    TARGET_TEMPERATURE_SUMMER_REGISTER,
    TARGET_TEMPERATURE_WINTER_REGISTER,
)

_LOGGER = logging.getLogger(__name__)

WATER_BYPASS = 0
WATER_CIRCULATING = 1


class ClimavenetaIMXWCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Climaveneta IMXW data."""

    fan_mode = FAN_AUTO
    hvac_mode: HVACMode = HVACMode.OFF
    hvac_action: HVACAction = HVACAction.OFF

    def __init__(self, hass: HomeAssistant, hub: ModbusHub, slaveid: int, name) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=SCAN_INTERVAL,
        )
        self.hub = hub
        self.slave_id = slaveid
        self.data_modbus = {"a": 1}
        self.name = name

    async def _async_update_data(self):
        """Fetch data from API endpoint."""

        if self.data_modbus is None:
            self.data_modbus = {}

        # setpoint and actuals
        self.data_modbus["summer_winter"] = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_READ_SEASON_REGISTER
        )

        if self.data_modbus["summer_winter"] == MODE_WINTER:  # winter
            self.data_modbus[
                "winter_temperature"
            ] = await self._async_read_temp_from_register(
                CALL_TYPE_REGISTER_HOLDING, TARGET_TEMPERATURE_WINTER_REGISTER
            )
            self.data_modbus["target_temperature"] = self.data_modbus[
                "winter_temperature"
            ]
        else:  # summer
            self.data_modbus[
                "summer_temperature"
            ] = await self._async_read_temp_from_register(
                CALL_TYPE_REGISTER_HOLDING, TARGET_TEMPERATURE_SUMMER_REGISTER
            )
            self.data_modbus["target_temperature"] = self.data_modbus[
                "summer_temperature"
            ]

        self.data_modbus[
            "current_temperature"
        ] = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, ACTUAL_AIR_TEMPERATURE_REGISTER
        )

        # state heating/cooling/fan only/off
        self.data_modbus["on_off"] = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_READ_ON_OFF_REGISTER
        )
        if self.data_modbus["on_off"]:
            self.data_modbus["fan_only"] = await self._async_read_int16_from_register(
                CALL_TYPE_REGISTER_HOLDING, STATE_READ_FAN_ONLY_REGISTER
            )
            self.data_modbus["ev_water"] = await self._async_read_int16_from_register(
                CALL_TYPE_REGISTER_HOLDING, STATE_READ_EV_WATER_REGISTER
            )
            if self.data_modbus["fan_only"] == MODE_ON:
                self.hvac_mode = HVACMode.FAN_ONLY
                self.hvac_action = HVACAction.FAN
            elif self.data_modbus["summer_winter"] == MODE_SUMMER:
                self.hvac_mode = HVACMode.COOL
                if self.data_modbus["ev_water"] == WATER_CIRCULATING:
                    self.hvac_action = HVACAction.COOLING
                else:
                    self.hvac_action = HVACAction.IDLE
            else:
                self.hvac_mode = HVACMode.HEAT
                if self.data_modbus["ev_water"] == WATER_CIRCULATING:
                    self.hvac_action = HVACAction.HEATING
                else:
                    self.hvac_action = HVACAction.IDLE
        else:
            self.hvac_mode = HVACMode.OFF
            self.hvac_action = HVACAction.OFF

        # fan speed

        fan_auto = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, STATE_READ_FAN_AUTO_REGISTER
        )
        if fan_auto == MODE_ON:
            self.fan_mode = FAN_AUTO
        else:
            fan_min = await self._async_read_int16_from_register(
                CALL_TYPE_REGISTER_HOLDING, STATE_READ_FAN_MIN_SPEED_REGISTER
            )
            if fan_min == MODE_ON:
                self.fan_mode = FAN_LOW
            else:
                fan_med = await self._async_read_int16_from_register(
                    CALL_TYPE_REGISTER_HOLDING, STATE_READ_FAN_MED_SPEED_REGISTER
                )
                if fan_med == MODE_ON:
                    self.fan_mode = FAN_MEDIUM
                else:
                    fan_max = await self._async_read_int16_from_register(
                        CALL_TYPE_REGISTER_HOLDING,
                        STATE_READ_FAN_MAX_SPEED_REGISTER,
                    )
                    if fan_max == MODE_ON:
                        self.fan_mode = FAN_HIGH
                    else:
                        self.fan_mode = FAN_AUTO  # should never arrive here...

        self.data_modbus["t1_alarm"] = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, ALARM_T1_REGISTER
        )

        self.data_modbus["t3_alarm"] = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, ALARM_T3_REGISTER
        )

        self.data_modbus["water_drain"] = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_HOLDING, ALARM_WATER_DRAIN_REGISTER
        )

        self.data_modbus[
            "exchanger_temperature"
        ] = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, ACTUAL_WATER_TEMPERATURE_REGISTER
        )

    # Based on _async_read_register in ModbusThermostat class
    async def _async_read_int16_from_register(
        self, register_type: str, register: int
    ) -> int:
        """Read register using the Modbus hub slave."""

        result = await self.hub.async_pb_call(self.slave_id, register, 1, register_type)

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
        result = 20.0

        if not result:
            return -1
        return result / 10.0
