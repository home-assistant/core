"""Support for Atlantic Electrical Towel Dryer."""

from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_BOOST,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..const import DOMAIN
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_DRYING = "drying"
PRESET_PROG = "prog"

OVERKIZ_TO_HVAC_MODE: dict[str, HVACMode] = {
    OverkizCommandParam.EXTERNAL: HVACMode.HEAT,  # manu
    OverkizCommandParam.INTERNAL: HVACMode.AUTO,  # prog (schedule, user program) - mapped as preset
    OverkizCommandParam.AUTO: HVACMode.AUTO,  # auto (intelligent, user behavior)
    OverkizCommandParam.STANDBY: HVACMode.OFF,  # off
}
HVAC_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODE.items()}

OVERKIZ_TO_PRESET_MODE: dict[str, str] = {
    OverkizCommandParam.PERMANENT_HEATING: PRESET_NONE,
    OverkizCommandParam.BOOST: PRESET_BOOST,
    OverkizCommandParam.DRYING: PRESET_DRYING,
}
PRESET_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODE.items()}

TEMPERATURE_SENSOR_DEVICE_INDEX = 7


class AtlanticElectricalTowelDryer(OverkizEntity, ClimateEntity):
    """Representation of Atlantic Electrical Towel Dryer."""

    _attr_hvac_modes = [*HVAC_MODE_TO_OVERKIZ]
    _attr_preset_modes = [PRESET_NONE, PRESET_PROG]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self.temperature_device = self.executor.linked_device(
            TEMPERATURE_SENSOR_DEVICE_INDEX
        )

        # Not all AtlanticElectricalTowelDryer models support temporary presets,
        # thus we check if the command is available and then extend the presets
        if self.executor.has_command(OverkizCommand.SET_TOWEL_DRYER_TEMPORARY_STATE):
            # Extend preset modes with supported temporary presets, avoiding duplicates
            self._attr_preset_modes += [
                mode
                for mode in PRESET_MODE_TO_OVERKIZ
                if mode not in self._attr_preset_modes
            ]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if OverkizState.CORE_OPERATING_MODE in self.device.states:
            return OVERKIZ_TO_HVAC_MODE[
                cast(str, self.executor.select_state(OverkizState.CORE_OPERATING_MODE))
            ]

        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_TOWEL_DRYER_OPERATING_MODE,
            HVAC_MODE_TO_OVERKIZ[hvac_mode],
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        state = (
            OverkizState.IO_EFFECTIVE_TEMPERATURE_SETPOINT
            if self.hvac_mode == HVACMode.AUTO
            else OverkizState.CORE_TARGET_TEMPERATURE
        )

        return cast(float, self.executor.select_state(state))

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.temperature_device is not None and (
            temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]
        ):
            return cast(float, temperature.value)

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        if self.hvac_mode == HVACMode.AUTO:
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATED_TARGET_TEMPERATURE, temperature
            )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.SET_TARGET_TEMPERATURE, temperature
            )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if (
            OverkizState.CORE_OPERATING_MODE in self.device.states
            and cast(str, self.executor.select_state(OverkizState.CORE_OPERATING_MODE))
            == OverkizCommandParam.INTERNAL
        ):
            return PRESET_PROG

        if PRESET_DRYING in self._attr_preset_modes:
            return OVERKIZ_TO_PRESET_MODE[
                cast(
                    str,
                    self.executor.select_state(
                        OverkizState.IO_TOWEL_DRYER_TEMPORARY_STATE
                    ),
                )
            ]

        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        # If the preset mode is set to prog, we need to set the operating mode to internal
        if preset_mode == PRESET_PROG:
            # If currently in a temporary preset (drying or boost), turn it off before turn on prog
            if self.preset_mode in (PRESET_DRYING, PRESET_BOOST):
                await self.executor.async_execute_command(
                    OverkizCommand.SET_TOWEL_DRYER_TEMPORARY_STATE,
                    OverkizCommandParam.PERMANENT_HEATING,
                )

            await self.executor.async_execute_command(
                OverkizCommand.SET_TOWEL_DRYER_OPERATING_MODE,
                OverkizCommandParam.INTERNAL,
            )

        # If the preset mode is set from prog to none, we need to set the operating mode to external
        # This will set the towel dryer to auto (intelligent mode)
        elif preset_mode == PRESET_NONE and self.preset_mode == PRESET_PROG:
            await self.executor.async_execute_command(
                OverkizCommand.SET_TOWEL_DRYER_OPERATING_MODE,
                OverkizCommandParam.AUTO,
            )

        # Normal behavior of setting a preset mode
        # for towel dryers that support temporary presets
        elif PRESET_DRYING in self._attr_preset_modes:
            await self.executor.async_execute_command(
                OverkizCommand.SET_TOWEL_DRYER_TEMPORARY_STATE,
                PRESET_MODE_TO_OVERKIZ[preset_mode],
            )
