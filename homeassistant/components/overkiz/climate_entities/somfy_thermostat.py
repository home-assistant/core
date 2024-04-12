"""Support for Somfy Smart Thermostat."""

from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..const import DOMAIN
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_FREEZE = "freeze"
PRESET_NIGHT = "night"


OVERKIZ_TO_HVAC_MODES: dict[str, HVACMode] = {
    OverkizCommandParam.ACTIVE: HVACMode.HEAT,
    OverkizCommandParam.INACTIVE: HVACMode.AUTO,
}
HVAC_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODES.items()}

OVERKIZ_TO_PRESET_MODES: dict[OverkizCommandParam, str] = {
    OverkizCommandParam.AT_HOME_MODE: PRESET_HOME,
    OverkizCommandParam.AWAY_MODE: PRESET_AWAY,
    OverkizCommandParam.FREEZE_MODE: PRESET_FREEZE,
    OverkizCommandParam.GEOFENCING_MODE: PRESET_NONE,
    OverkizCommandParam.MANUAL_MODE: PRESET_NONE,
    OverkizCommandParam.SLEEPING_MODE: PRESET_NIGHT,
    OverkizCommandParam.SUDDEN_DROP_MODE: PRESET_NONE,
}

PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODES.items()}
TARGET_TEMP_TO_OVERKIZ = {
    PRESET_HOME: OverkizState.SOMFY_THERMOSTAT_AT_HOME_TARGET_TEMPERATURE,
    PRESET_AWAY: OverkizState.SOMFY_THERMOSTAT_AWAY_MODE_TARGET_TEMPERATURE,
    PRESET_FREEZE: OverkizState.SOMFY_THERMOSTAT_FREEZE_MODE_TARGET_TEMPERATURE,
    PRESET_NIGHT: OverkizState.SOMFY_THERMOSTAT_SLEEPING_MODE_TARGET_TEMPERATURE,
}

# controllableName is somfythermostat:SomfyThermostatTemperatureSensor
TEMPERATURE_SENSOR_DEVICE_INDEX = 2


class SomfyThermostat(OverkizEntity, ClimateEntity):
    """Representation of Somfy Smart Thermostat."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [*HVAC_MODES_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    _attr_translation_key = DOMAIN
    _enable_turn_on_off_backwards_compatibility = False

    # Both min and max temp values have been retrieved from the Somfy Application.
    _attr_min_temp = 15.0
    _attr_max_temp = 26.0

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self.temperature_device = self.executor.linked_device(
            TEMPERATURE_SENSOR_DEVICE_INDEX
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        return OVERKIZ_TO_HVAC_MODES[
            cast(
                str, self.executor.select_state(OverkizState.CORE_DEROGATION_ACTIVATION)
            )
        ]

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        if self.hvac_mode == HVACMode.AUTO:
            state_key = OverkizState.SOMFY_THERMOSTAT_HEATING_MODE
        else:
            state_key = OverkizState.SOMFY_THERMOSTAT_DEROGATION_HEATING_MODE

        state = cast(str, self.executor.select_state(state_key))

        return OVERKIZ_TO_PRESET_MODES[OverkizCommandParam(state)]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.temperature_device is not None and (
            temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]
        ):
            return cast(float, temperature.value)
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVACMode.AUTO:
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
            OverkizCommand.SET_DEROGATION,
            temperature,
            OverkizCommandParam.FURTHER_NOTICE,
        )
        await self.executor.async_execute_command(
            OverkizCommand.SET_MODE_TEMPERATURE,
            OverkizCommandParam.MANUAL_MODE,
            temperature,
        )
        await self.executor.async_execute_command(OverkizCommand.REFRESH_STATE)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.AUTO:
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
                OverkizCommandParam.FURTHER_NOTICE,
            )
        elif preset_mode == PRESET_NONE:
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATION,
                self.target_temperature,
                OverkizCommandParam.FURTHER_NOTICE,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_MODE_TEMPERATURE,
                OverkizCommandParam.MANUAL_MODE,
                self.target_temperature,
            )
        await self.executor.async_execute_command(OverkizCommand.REFRESH_STATE)
