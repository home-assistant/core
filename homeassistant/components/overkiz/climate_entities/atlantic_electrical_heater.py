"""Support for Atlantic Electrical Heater."""
from __future__ import annotations

from typing import cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import TEMP_CELSIUS

from ..entity import OverkizEntity

PRESET_FROST_PROTECTION = "frost_protection"

OVERKIZ_TO_HVAC_MODES: dict[str, HVACMode] = {
    OverkizCommandParam.ON: HVACMode.HEAT,
    OverkizCommandParam.COMFORT: HVACMode.HEAT,
    OverkizCommandParam.OFF: HVACMode.OFF,
}
HVAC_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODES.items()}

OVERKIZ_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.OFF: PRESET_NONE,
    OverkizCommandParam.FROSTPROTECTION: PRESET_FROST_PROTECTION,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
}

PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODES.items()}


class AtlanticElectricalHeater(OverkizEntity, ClimateEntity):
    """Representation of Atlantic Electrical Heater."""

    _attr_hvac_modes = [*HVAC_MODES_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    _attr_supported_features = ClimateEntityFeature.PRESET_MODE
    _attr_temperature_unit = TEMP_CELSIUS

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        return OVERKIZ_TO_HVAC_MODES[
            cast(str, self.executor.select_state(OverkizState.CORE_ON_OFF))
        ]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_HEATING_LEVEL, HVAC_MODES_TO_OVERKIZ[hvac_mode]
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return OVERKIZ_TO_PRESET_MODES[
            cast(str, self.executor.select_state(OverkizState.IO_TARGET_HEATING_LEVEL))
        ]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_HEATING_LEVEL, PRESET_MODES_TO_OVERKIZ[preset_mode]
        )
