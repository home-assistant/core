"""Support for TaHoma Smart Thermostat."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizState

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

COMMAND_EXIT_DEROGATION = "exitDerogation"
COMMAND_REFRESH_STATE = "refreshState"
COMMAND_SET_DEROGATION = "setDerogation"
COMMAND_SET_MODE_TEMPERATURE = "setModeTemperature"

CORE_DEROGATED_TARGET_TEMPERATURE_STATE = "core:DerogatedTargetTemperatureState"
CORE_DEROGATION_ACTIVATION_STATE = "core:DerogationActivationState"

PRESET_FREEZE = "freeze"
PRESET_NIGHT = "night"

ST_HEATING_MODE_STATE = "somfythermostat:HeatingModeState"
ST_DEROGATION_HEATING_MODE_STATE = "somfythermostat:DerogationHeatingModeState"

STATE_DEROGATION_FURTHER_NOTICE = "further_notice"
STATE_DEROGATION_ACTIVE = "active"
STATE_DEROGATION_INACTIVE = "inactive"
STATE_PRESET_AT_HOME = "atHomeMode"
STATE_PRESET_AWAY = "awayMode"
STATE_PRESET_FREEZE = "freezeMode"
STATE_PRESET_MANUAL = "manualMode"
STATE_PRESET_SLEEPING_MODE = "sleepingMode"
STATE_PRESET_SUDDEN_DROP_MODE = "suddenDropMode"

OVERKIZ_TO_HVAC_MODES = {
    STATE_DEROGATION_ACTIVE: HVAC_MODE_HEAT,
    STATE_DEROGATION_INACTIVE: HVAC_MODE_AUTO,
}
OVERKIZ_TO_PRESET_MODES = {
    STATE_PRESET_AT_HOME: PRESET_HOME,
    STATE_PRESET_AWAY: PRESET_AWAY,
    STATE_PRESET_FREEZE: PRESET_FREEZE,
    STATE_PRESET_MANUAL: PRESET_NONE,
    STATE_PRESET_SLEEPING_MODE: PRESET_NIGHT,
    STATE_PRESET_SUDDEN_DROP_MODE: PRESET_NONE,
}
PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODES.items()}
TARGET_TEMP_TO_OVERKIZ = {
    PRESET_HOME: "somfythermostat:AtHomeTargetTemperatureState",
    PRESET_AWAY: "somfythermostat:AwayModeTargetTemperatureState",
    PRESET_FREEZE: "somfythermostat:FreezeModeTargetTemperatureState",
    PRESET_NIGHT: "somfythermostat:SleepingModeTargetTemperatureState",
}


class SomfyThermostat(OverkizEntity, ClimateEntity):
    """Representation of Somfy Smart Thermostat."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE
    _attr_hvac_modes = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
    _attr_preset_modes = [
        PRESET_NONE,
        PRESET_FREEZE,
        PRESET_NIGHT,
        PRESET_AWAY,
        PRESET_HOME,
    ]
    _attr_min_temp = 15.0
    _attr_max_temp = 26.0

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self.temperature_device = self.executor.linked_device(2)
        if self.hvac_mode == HVAC_MODE_AUTO:
            if self.preset_mode == PRESET_NONE:
                self._saved_target_temp = None
            else:
                self._saved_target_temp = self.executor.select_state(
                    TARGET_TEMP_TO_OVERKIZ[self.preset_mode]
                )
        else:
            self._saved_target_temp = self.executor.select_state(
                CORE_DEROGATED_TARGET_TEMPERATURE_STATE
            )

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return OVERKIZ_TO_HVAC_MODES[
            self.executor.select_state(CORE_DEROGATION_ACTIVATION_STATE)
        ]

    @property
    def hvac_action(self) -> str:
        """Return the current running hvac operation if supported."""
        if not self.current_temperature or not self.target_temperature:
            return CURRENT_HVAC_IDLE
        if self.current_temperature < self.target_temperature:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return OVERKIZ_TO_PRESET_MODES[self.executor.select_state(ST_HEATING_MODE_STATE)]
        return OVERKIZ_TO_PRESET_MODES[
            self.executor.select_state(ST_DEROGATION_HEATING_MODE_STATE)
        ]

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return cast(
            float,
            self.temperature_device.states.get(OverkizState.CORE_TEMPERATURE).value,
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            if self.preset_mode == PRESET_NONE:
                return None
            return self.executor.select_state(TARGET_TEMP_TO_OVERKIZ[self.preset_mode])
        return self.executor.select_state(CORE_DEROGATED_TARGET_TEMPERATURE_STATE)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        await self.executor.async_execute_command(
            COMMAND_SET_DEROGATION, temperature, STATE_DEROGATION_FURTHER_NOTICE
        )
        await self.executor.async_execute_command(
            COMMAND_SET_MODE_TEMPERATURE, STATE_PRESET_MANUAL, temperature
        )
        await self.executor.async_execute_command(COMMAND_REFRESH_STATE)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == self.hvac_mode:
            return
        if hvac_mode == HVAC_MODE_AUTO:
            self._saved_target_temp = self.target_temperature
            await self.executor.async_execute_command(COMMAND_EXIT_DEROGATION)
            await self.executor.async_execute_command(COMMAND_REFRESH_STATE)
        elif hvac_mode == HVAC_MODE_HEAT:
            await self.async_set_preset_mode(PRESET_NONE)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.preset_mode == preset_mode:
            return
        if preset_mode in [PRESET_FREEZE, PRESET_NIGHT, PRESET_AWAY, PRESET_HOME]:
            self._saved_target_temp = self.target_temperature
            await self.executor.async_execute_command(
                COMMAND_SET_DEROGATION,
                PRESET_MODES_TO_OVERKIZ[preset_mode],
                STATE_DEROGATION_FURTHER_NOTICE,
            )
        elif preset_mode == PRESET_NONE:
            await self.executor.async_execute_command(
                COMMAND_SET_DEROGATION,
                self._saved_target_temp,
                STATE_DEROGATION_FURTHER_NOTICE,
            )
            await self.executor.async_execute_command(
                COMMAND_SET_MODE_TEMPERATURE,
                STATE_PRESET_MANUAL,
                self._saved_target_temp,
            )
        await self.executor.async_execute_command(COMMAND_REFRESH_STATE)
