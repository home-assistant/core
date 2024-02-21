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

OVERKIZ_TO_HVAC_MODE: dict[str, HVACMode] = {
    OverkizCommandParam.EXTERNAL: HVACMode.HEAT,  # manu
    OverkizCommandParam.INTERNAL: HVACMode.AUTO,  # prog
    OverkizCommandParam.STANDBY: HVACMode.OFF,
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
    _attr_preset_modes = [*PRESET_MODE_TO_OVERKIZ]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self.temperature_device = self.executor.linked_device(
            TEMPERATURE_SENSOR_DEVICE_INDEX
        )

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        # Not all AtlanticElectricalTowelDryer models support presets, thus we need to check if the command is available
        if self.executor.has_command(OverkizCommand.SET_TOWEL_DRYER_TEMPORARY_STATE):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

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
    def target_temperature(self) -> None:
        """Return the temperature."""
        if self.hvac_mode == HVACMode.AUTO:
            self.executor.select_state(OverkizState.IO_EFFECTIVE_TEMPERATURE_SETPOINT)
        else:
            self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]:
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
        return OVERKIZ_TO_PRESET_MODE[
            cast(
                str,
                self.executor.select_state(OverkizState.IO_TOWEL_DRYER_TEMPORARY_STATE),
            )
        ]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_TOWEL_DRYER_TEMPORARY_STATE,
            PRESET_MODE_TO_OVERKIZ[preset_mode],
        )
