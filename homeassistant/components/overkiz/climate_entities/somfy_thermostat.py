"""Support for TaHoma Smart Thermostat."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizState

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

PRESET_FREEZE = "freeze"
PRESET_NIGHT = "night"

STATE_DEROGATION_FURTHER_NOTICE = "further_notice"
STATE_DEROGATION_ACTIVE = "active"
STATE_DEROGATION_INACTIVE = "inactive"
STATE_PRESET_AT_HOME = "atHomeMode"
STATE_PRESET_AWAY = "awayMode"
STATE_PRESET_FREEZE = "freezeMode"
STATE_PRESET_MANUAL = "manualMode"
STATE_PRESET_SLEEPING_MODE = "sleepingMode"
STATE_PRESET_SUDDEN_DROP_MODE = "suddenDropMode"

OVERKIZ_TO_HVAC_MODES: dict[str, str] = {
    STATE_DEROGATION_ACTIVE: HVAC_MODE_HEAT,
    STATE_DEROGATION_INACTIVE: HVAC_MODE_AUTO,
}
OVERKIZ_TO_PRESET_MODES: dict[str, str] = {
    STATE_PRESET_AT_HOME: PRESET_HOME,
    STATE_PRESET_AWAY: PRESET_AWAY,
    STATE_PRESET_FREEZE: PRESET_FREEZE,
    STATE_PRESET_MANUAL: PRESET_NONE,
    STATE_PRESET_SLEEPING_MODE: PRESET_NIGHT,
    STATE_PRESET_SUDDEN_DROP_MODE: PRESET_NONE,
}
PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODES.items()}
TARGET_TEMP_TO_OVERKIZ = {
    PRESET_HOME: OverkizState.SOMFY_THERMOSTAT_AT_HOME_TARGET_TEMPERATURE,
    PRESET_AWAY: OverkizState.SOMFY_THERMOSTAT_AWAY_MODE_TARGET_TEMPERATURE,
    PRESET_FREEZE: OverkizState.SOMFY_THERMOSTAT_FREEZE_MODE_TARGET_TEMPERATURE,
    PRESET_NIGHT: OverkizState.SOMFY_THERMOSTAT_SLEEPING_MODE_TARGET_TEMPERATURE,
}


class SomfyThermostat(OverkizEntity, ClimateEntity):
    """Representation of Somfy Smart Thermostat."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE
    _attr_hvac_modes = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    # Both min and max temp values have been retrieved from the Somfy Application.
    _attr_min_temp = 15.0
    _attr_max_temp = 26.0

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self.temperature_device = self.executor.linked_device(2)

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return OVERKIZ_TO_HVAC_MODES[
            cast(
                str, self.executor.select_state(OverkizState.CORE_DEROGATION_ACTIVATION)
            )
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
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return OVERKIZ_TO_PRESET_MODES[
                cast(
                    str,
                    self.executor.select_state(
                        OverkizState.SOMFY_THERMOSTAT_HEATING_MODE
                    ),
                )
            ]
        return OVERKIZ_TO_PRESET_MODES[
            cast(
                str,
                self.executor.select_state(
                    OverkizState.SOMFY_THERMOSTAT_DEROGATION_HEATING_MODE
                ),
            )
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]:
            return cast(float, temperature.value)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            if self.preset_mode == PRESET_NONE:
                return None
            return cast(
                float,
                self.executor.select_state(TARGET_TEMP_TO_OVERKIZ[self.preset_mode]),
            )
        return cast(
            float,
            self.executor.select_state(OverkizState.CORE_DEROGATED_TARGET_TEMPERATURE),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        await self.executor.async_execute_command(
            OverkizCommand.SET_DEROGATION, temperature, STATE_DEROGATION_FURTHER_NOTICE
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_MODE_TEMPERATURE, STATE_PRESET_MANUAL, temperature
        )
        await self.executor.async_execute_command(OverkizCommand.REFRESH_STATE)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            await self.executor.async_execute_command(OverkizCommand.EXIT_DEROGATION)
            await self.executor.async_execute_command(OverkizCommand.REFRESH_STATE)
        else:
            await self.async_set_preset_mode(PRESET_NONE)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode in [PRESET_FREEZE, PRESET_NIGHT, PRESET_AWAY, PRESET_HOME]:
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATION,
                PRESET_MODES_TO_OVERKIZ[preset_mode],
                STATE_DEROGATION_FURTHER_NOTICE,
            )
        elif preset_mode == PRESET_NONE:
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATION,
                self.target_temperature,
                STATE_DEROGATION_FURTHER_NOTICE,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_MODE_TEMPERATURE,
                STATE_PRESET_MANUAL,
                self.target_temperature,
            )
        await self.executor.async_execute_command(OverkizCommand.REFRESH_STATE)
