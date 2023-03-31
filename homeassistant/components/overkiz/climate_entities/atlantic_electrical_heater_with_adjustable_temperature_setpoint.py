"""Support for Atlantic Electrical Heater (With Adjustable Temperature Setpoint)."""
from __future__ import annotations

from typing import Any

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..const import DOMAIN
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_AUTO = "auto"
PRESET_COMFORT1 = "comfort-1"
PRESET_COMFORT2 = "comfort-2"
PRESET_FROST_PROTECTION = "frost_protection"
PRESET_PROG = "prog"
PRESET_EXTERNAL = "external"


# Map Overkiz presets to Home Assistant presets
OVERKIZ_TO_PRESET_MODE: dict[str, str] = {
    OverkizCommandParam.OFF: PRESET_NONE,
    OverkizCommandParam.FROSTPROTECTION: PRESET_FROST_PROTECTION,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.COMFORT_1: PRESET_COMFORT1,
    OverkizCommandParam.COMFORT_2: PRESET_COMFORT2,
    OverkizCommandParam.AUTO: PRESET_AUTO,
    OverkizCommandParam.BOOST: PRESET_BOOST,
    OverkizCommandParam.EXTERNAL: PRESET_EXTERNAL,
    OverkizCommandParam.INTERNAL: PRESET_PROG,
}

PRESET_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODE.items()}

# Map Overkiz HVAC modes to Home Assistant HVAC modes
OVERKIZ_TO_HVAC_MODE: dict[str, str] = {
    OverkizCommandParam.ON: HVACMode.HEAT,
    OverkizCommandParam.OFF: HVACMode.OFF,
    OverkizCommandParam.AUTO: HVACMode.AUTO,
    OverkizCommandParam.BASIC: HVACMode.HEAT,
    OverkizCommandParam.STANDBY: HVACMode.OFF,
    OverkizCommandParam.EXTERNAL: HVACMode.AUTO,
    OverkizCommandParam.INTERNAL: HVACMode.AUTO,
}

HVAC_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODE.items()}

TEMPERATURE_SENSOR_DEVICE_INDEX = 2


class AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint(
    OverkizEntity, ClimateEntity
):
    """Representation of Atlantic Electrical Heater (With Adjustable Temperature Setpoint)."""

    _attr_hvac_modes = [*HVAC_MODE_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODE_TO_OVERKIZ]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_translation_key = DOMAIN

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self.temperature_device = self.executor.linked_device(
            TEMPERATURE_SENSOR_DEVICE_INDEX
        )

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        states = self.device.states
        if (state := states[OverkizState.CORE_OPERATING_MODE]) and state.value_as_str:
            return OVERKIZ_TO_HVAC_MODE[state.value_as_str]
        if (state := states[OverkizState.CORE_ON_OFF]) and state.value_as_str:
            return OVERKIZ_TO_HVAC_MODE[state.value_as_str]
        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_OPERATING_MODE, HVAC_MODE_TO_OVERKIZ[hvac_mode]
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""

        states = self.device.states

        if (
            operating_mode := states[OverkizState.CORE_OPERATING_MODE]
        ) and operating_mode.value_as_str == OverkizCommandParam.EXTERNAL:
            return PRESET_EXTERNAL

        if (
            state := states[OverkizState.IO_TARGET_HEATING_LEVEL]
        ) and state.value_as_str:
            return OVERKIZ_TO_PRESET_MODE[state.value_as_str]
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

        if preset_mode == PRESET_EXTERNAL:
            command = OverkizCommand.SET_SCHEDULING_TYPE
        elif preset_mode in [PRESET_AUTO, PRESET_PROG]:
            command = OverkizCommand.SET_OPERATING_MODE
        else:
            command = OverkizCommand.SET_HEATING_LEVEL
        await self.executor.async_execute_command(
            command, PRESET_MODE_TO_OVERKIZ[preset_mode]
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature."""
        if state := self.device.states[OverkizState.CORE_TARGET_TEMPERATURE]:
            return state.value_as_float
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]:
            return temperature.value_as_float
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, temperature
        )
