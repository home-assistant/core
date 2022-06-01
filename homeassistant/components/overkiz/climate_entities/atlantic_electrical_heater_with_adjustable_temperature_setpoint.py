"""Support for Atlantic Electrical Heater (With Adjustable Temperature Setpoint)."""
from __future__ import annotations

from typing import cast

from pyoverkiz.enums import OverkizCommand, OverkizState

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_AUTO = "auto"
PRESET_COMFORT1 = "comfort-1"
PRESET_COMFORT2 = "comfort-2"
PRESET_FROST_PROTECTION = "frost_protection"
PRESET_PROG = "prog"

PRESET_STATE_ECO = "eco"
PRESET_STATE_BOOST = "boost"
PRESET_STATE_COMFORT = "comfort"


# Map TaHoma presets to Home Assistant presets
OVERKIZ_TO_PRESET_MODE = {
    "off": PRESET_NONE,
    "frostprotection": PRESET_FROST_PROTECTION,
    "eco": PRESET_ECO,
    "comfort": PRESET_COMFORT,
    "comfort-1": PRESET_COMFORT1,
    "comfort-2": PRESET_COMFORT2,
    "auto": PRESET_AUTO,
    "boost": PRESET_BOOST,
    "internal": PRESET_PROG,
}

PRESET_MODE_TO_TAHOMA = {v: k for k, v in OVERKIZ_TO_PRESET_MODE.items()}

# Map TaHoma HVAC modes to Home Assistant HVAC modes
OVERKIZ_TO_HVAC_MODE = {
    "on": HVACMode.HEAT,
    "off": HVACMode.OFF,
    "auto": HVACMode.AUTO,
    "basic": HVACMode.HEAT,
    "standby": HVACMode.OFF,
    "internal": HVACMode.AUTO,
}

HVAC_MODE_TO_TAHOMA = {v: k for k, v in OVERKIZ_TO_HVAC_MODE.items()}


class AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint(
    OverkizEntity, ClimateEntity
):
    """Representation of Atlantic Electrical Heater (With Adjustable Temperature Setpoint)."""

    _attr_hvac_modes = [*HVAC_MODE_TO_TAHOMA]
    _attr_preset_modes = [*PRESET_MODE_TO_TAHOMA]
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )

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
                OverkizCommand.SET_OPERATING_MODE, HVAC_MODE_TO_TAHOMA[hvac_mode]
            )
        else:
            if hvac_mode == HVACMode.OFF:
                await self.executor.async_execute_command(
                    OverkizCommand.OFF,
                )
            else:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_HEATING_LEVEL, PRESET_STATE_COMFORT
                )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return OVERKIZ_TO_PRESET_MODE[
            self.executor.select_state(OverkizState.IO_TARGET_HEATING_LEVEL)
        ]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode in [PRESET_AUTO, PRESET_PROG]:
            await self.executor.async_execute_command(
                OverkizCommand.SET_OPERATING_MODE, PRESET_MODE_TO_TAHOMA[preset_mode]
            )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.SET_HEATING_LEVEL, PRESET_MODE_TO_TAHOMA[preset_mode]
            )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature."""
        if OverkizState.CORE_TARGET_TEMPERATURE in self.device.states:
            return self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)
        return None

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
