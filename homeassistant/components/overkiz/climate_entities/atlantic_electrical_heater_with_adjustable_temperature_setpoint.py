"""Support for Atlantic Electrical Heater With Adjustable Temperature Setpoint."""
from __future__ import annotations

from typing import cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_AUTO = "auto"
PRESET_FROST_PROTECTION = "frost_protection"
PRESET_PROG = "prog"

# Map OVERKIZ presets to Home Assistant presets
OVERKIZ_TO_PRESET_MODE = {
    OverkizCommandParam.OFF: PRESET_NONE,
    OverkizCommandParam.FROSTPROTECTION: PRESET_FROST_PROTECTION,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.AUTO: PRESET_AUTO,
    OverkizCommandParam.BOOST: PRESET_BOOST,
    OverkizCommandParam.INTERNAL: PRESET_PROG,
}

PRESET_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODE.items()}

# Map OVERKIZ HVAC modes to Home Assistant HVAC modes
OVERKIZ_TO_HVAC_MODE = {
    OverkizCommandParam.ON: HVAC_MODE_HEAT,
    OverkizCommandParam.OFF: HVAC_MODE_OFF,
    OverkizCommandParam.AUTO: HVAC_MODE_AUTO,
    "basic": HVAC_MODE_HEAT,
    OverkizCommandParam.STANDBY: HVAC_MODE_OFF,
    OverkizCommandParam.INTERNAL: HVAC_MODE_AUTO,
}

HVAC_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODE.items()}


class AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint(
    OverkizEntity, ClimateEntity
):
    """Representation of Atlantic Electrical Heater With Adjustable Temperature Setpoint."""

    _attr_hvac_modes = [*HVAC_MODE_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODE_TO_OVERKIZ]
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)
        self.temperature_device = self.executor.linked_device(2)

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        if OverkizState.CORE_OPERATING_MODE in self.device.states:
            return OVERKIZ_TO_HVAC_MODE[
                self.executor.select_state(OverkizState.CORE_OPERATING_MODE)
            ]
        if OverkizState.CORE_ON_OFF in self.device.states:
            return OVERKIZ_TO_HVAC_MODE[
                self.executor.select_state(OverkizState.CORE_ON_OFF)
            ]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if OverkizState.CORE_OPERATING_MODE in self.device.states:
            await self.executor.async_execute_command(
                OverkizCommand.SET_OPERATING_MODE, HVAC_MODE_TO_OVERKIZ[hvac_mode]
            )
        else:
            if hvac_mode == HVAC_MODE_OFF:
                await self.executor.async_execute_command(
                    OverkizCommand.OFF,
                )
            else:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_HEATING_LEVEL, OverkizCommandParam.COMFORT
                )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return OVERKIZ_TO_PRESET_MODE[
            self.executor.select_state(OverkizState.IO_TARGET_HEATING_LEVEL)
        ]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if [PRESET_AUTO, PRESET_PROG] in preset_mode:
            await self.executor.async_execute_command(
                OverkizCommand.SET_OPERATING_MODE, PRESET_MODE_TO_OVERKIZ[preset_mode]
            )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_LEVEL, PRESET_MODE_TO_OVERKIZ[preset_mode]
            )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature."""
        return self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]:
            return cast(float, temperature.value)

        return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, temperature
        )
