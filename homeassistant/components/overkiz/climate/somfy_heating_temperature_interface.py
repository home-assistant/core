"""Support for Somfy Heating Temperature Interface."""

from __future__ import annotations

from typing import Any

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

OVERKIZ_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.SECURED: PRESET_AWAY,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.FREE: PRESET_NONE,
}

PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODES.items()}

OVERKIZ_TO_HVAC_MODES: dict[str, HVACMode] = {
    OverkizCommandParam.AUTO: HVACMode.AUTO,
    OverkizCommandParam.MANU: HVACMode.HEAT_COOL,
}

HVAC_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODES.items()}

OVERKIZ_TO_HVAC_ACTION: dict[str, HVACAction] = {
    OverkizCommandParam.COOLING: HVACAction.COOLING,
    OverkizCommandParam.HEATING: HVACAction.HEATING,
}

MAP_PRESET_TEMPERATURES: dict[str, str] = {
    PRESET_COMFORT: OverkizState.CORE_COMFORT_ROOM_TEMPERATURE,
    PRESET_ECO: OverkizState.CORE_ECO_ROOM_TEMPERATURE,
    PRESET_AWAY: OverkizState.CORE_SECURED_POSITION_TEMPERATURE,
}

SETPOINT_MODE_TO_OVERKIZ_COMMAND: dict[str, str] = {
    OverkizCommandParam.COMFORT: OverkizCommand.SET_COMFORT_TEMPERATURE,
    OverkizCommandParam.ECO: OverkizCommand.SET_ECO_TEMPERATURE,
    OverkizCommandParam.SECURED: OverkizCommand.SET_SECURED_POSITION_TEMPERATURE,
}

TEMPERATURE_SENSOR_DEVICE_INDEX = 2


class SomfyHeatingTemperatureInterface(OverkizEntity, ClimateEntity):
    """Representation of Somfy Heating Temperature Interface.

    The thermostat has 3 ways of working:
      - Auto: Switch to eco/comfort temperature on a schedule (day/hour of the day)
      - Manual comfort: The thermostat use the temperature of the comfort setting (19°C degree by default)
      - Manual eco: The thermostat use the temperature of the eco setting (17°C by default)
      - Freeze protection: The thermostat use the temperature of the freeze protection (7°C by default)

    There's also the possibility to change the working mode, this can be used to change from a heated
    floor to a cooling floor in the summer.
    """

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [*HVAC_MODES_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    # Both min and max temp values have been retrieved from the Somfy Application.
    _attr_min_temp = 15.0
    _attr_max_temp = 26.0
    _enable_turn_on_off_backwards_compatibility = False

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
        """Return hvac operation i.e. heat, cool mode."""
        state = self.device.states[OverkizState.CORE_ON_OFF]
        if state and state.value_as_str == OverkizCommandParam.OFF:
            return HVACMode.OFF

        if (
            state := self.device.states[
                OverkizState.OVP_HEATING_TEMPERATURE_INTERFACE_ACTIVE_MODE
            ]
        ) and state.value_as_str:
            return OVERKIZ_TO_HVAC_MODES[state.value_as_str]

        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_ACTIVE_MODE, HVAC_MODES_TO_OVERKIZ[hvac_mode]
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if (
            state := self.device.states[
                OverkizState.OVP_HEATING_TEMPERATURE_INTERFACE_SETPOINT_MODE
            ]
        ) and state.value_as_str:
            return OVERKIZ_TO_PRESET_MODES[state.value_as_str]
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_MANU_AND_SET_POINT_MODES,
            PRESET_MODES_TO_OVERKIZ[preset_mode],
        )

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if (
            current_operation := self.device.states[
                OverkizState.OVP_HEATING_TEMPERATURE_INTERFACE_OPERATING_MODE
            ]
        ) and current_operation.value_as_str:
            return OVERKIZ_TO_HVAC_ACTION[current_operation.value_as_str]

        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""

        # Allow to get the current target temperature for the current preset
        # The preset can be switched manually or on a schedule (auto).
        # This allows to reflect the current target temperature automatically
        if not self.preset_mode:
            return None

        mode = PRESET_MODES_TO_OVERKIZ[self.preset_mode]
        if mode not in MAP_PRESET_TEMPERATURES:
            return None

        if state := self.device.states[MAP_PRESET_TEMPERATURES[mode]]:
            return state.value_as_float
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.temperature_device is not None and (
            temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]
        ):
            return temperature.value_as_float
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        if (
            mode := self.device.states[
                OverkizState.OVP_HEATING_TEMPERATURE_INTERFACE_SETPOINT_MODE
            ]
        ) and mode.value_as_str:
            await self.executor.async_execute_command(
                SETPOINT_MODE_TO_OVERKIZ_COMMAND[mode.value_as_str], temperature
            )
            return
