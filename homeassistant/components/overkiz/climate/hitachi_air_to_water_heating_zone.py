"""Support for HitachiAirToWaterHeatingZone."""

from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..const import DOMAIN
from ..entity import OverkizDataUpdateCoordinator, OverkizEntity

OVERKIZ_TO_HVAC_MODE: dict[str, HVACMode] = {
    OverkizCommandParam.MANU: HVACMode.HEAT,
    OverkizCommandParam.AUTO: HVACMode.AUTO,
}

HVAC_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODE.items()}

OVERKIZ_TO_PRESET_MODE: dict[str, str] = {
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.ECO: PRESET_ECO,
}

PRESET_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODE.items()}


class HitachiAirToWaterHeatingZone(OverkizEntity, ClimateEntity):
    """Representation of HitachiAirToWaterHeatingZone."""

    _attr_hvac_modes = [*HVAC_MODE_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODE_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_precision = 0.1
    _attr_target_temperature_step = 0.5
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        if self._attr_device_info:
            self._attr_device_info["manufacturer"] = "Hitachi"

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if (
            state := self.device.states[OverkizState.MODBUS_AUTO_MANU_MODE_ZONE_1]
        ) and state.value_as_str:
            return OVERKIZ_TO_HVAC_MODE[state.value_as_str]

        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_AUTO_MANU_MODE, HVAC_MODE_TO_OVERKIZ[hvac_mode]
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if (
            state := self.device.states[OverkizState.MODBUS_YUTAKI_TARGET_MODE]
        ) and state.value_as_str:
            return OVERKIZ_TO_PRESET_MODE[state.value_as_str]

        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_MODE, PRESET_MODE_TO_OVERKIZ[preset_mode]
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        current_temperature = self.device.states[
            OverkizState.MODBUS_ROOM_AMBIENT_TEMPERATURE_STATUS_ZONE_1
        ]

        if current_temperature:
            return current_temperature.value_as_float

        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        target_temperature = self.device.states[
            OverkizState.MODBUS_THERMOSTAT_SETTING_CONTROL_ZONE_1
        ]

        if target_temperature:
            return target_temperature.value_as_float

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = cast(float, kwargs.get(ATTR_TEMPERATURE))

        await self.executor.async_execute_command(
            OverkizCommand.SET_THERMOSTAT_SETTING_CONTROL_ZONE_1, float(temperature)
        )
