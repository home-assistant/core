"""Support for AtlanticHeatRecoveryVentilation."""

from __future__ import annotations

from typing import cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    FAN_AUTO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from ..const import DOMAIN
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

FAN_BOOST = "home_boost"
FAN_KITCHEN = "kitchen_boost"
FAN_AWAY = "away"
FAN_BYPASS = "bypass_boost"

PRESET_AUTO = "auto"
PRESET_PROG = "prog"
PRESET_MANUAL = "manual"

OVERKIZ_TO_FAN_MODES: dict[str, str] = {
    OverkizCommandParam.AUTO: FAN_AUTO,
    OverkizCommandParam.AWAY: FAN_AWAY,
    OverkizCommandParam.BOOST: FAN_BOOST,
    OverkizCommandParam.HIGH: FAN_KITCHEN,
    "": FAN_BYPASS,
}

FAN_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_FAN_MODES.items()}

TEMPERATURE_SENSOR_DEVICE_INDEX = 4


class AtlanticHeatRecoveryVentilation(OverkizEntity, ClimateEntity):
    """Representation of a AtlanticHeatRecoveryVentilation device."""

    _attr_fan_modes = [*FAN_MODES_TO_OVERKIZ]
    _attr_hvac_mode = HVACMode.FAN_ONLY
    _attr_hvac_modes = [HVACMode.FAN_ONLY]
    _attr_preset_modes = [PRESET_AUTO, PRESET_PROG, PRESET_MANUAL]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
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

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.temperature_device is not None and (
            temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]
        ):
            return cast(float, temperature.value)

        return None

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Not implemented since there is only one hvac_mode."""

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        ventilation_configuration = self.executor.select_state(
            OverkizState.IO_VENTILATION_CONFIGURATION_MODE
        )

        if ventilation_configuration == OverkizCommandParam.COMFORT:
            return PRESET_AUTO

        if ventilation_configuration == OverkizCommandParam.STANDARD:
            return PRESET_MANUAL

        ventilation_mode = cast(
            dict, self.executor.select_state(OverkizState.IO_VENTILATION_MODE)
        )
        prog = ventilation_mode.get(OverkizCommandParam.PROG)

        if prog == OverkizCommandParam.ON:
            return PRESET_PROG

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == PRESET_AUTO:
            await self.executor.async_execute_command(
                OverkizCommand.SET_VENTILATION_CONFIGURATION_MODE,
                OverkizCommandParam.COMFORT,
            )
            await self._set_ventilation_mode(prog=OverkizCommandParam.OFF)

        if preset_mode == PRESET_PROG:
            await self.executor.async_execute_command(
                OverkizCommand.SET_VENTILATION_CONFIGURATION_MODE,
                OverkizCommandParam.STANDARD,
            )
            await self._set_ventilation_mode(prog=OverkizCommandParam.ON)

        if preset_mode == PRESET_MANUAL:
            await self.executor.async_execute_command(
                OverkizCommand.SET_VENTILATION_CONFIGURATION_MODE,
                OverkizCommandParam.STANDARD,
            )
            await self._set_ventilation_mode(prog=OverkizCommandParam.OFF)

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_VENTILATION_STATE,
        )
        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_VENTILATION_CONFIGURATION_MODE,
        )

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        ventilation_mode = cast(
            dict, self.executor.select_state(OverkizState.IO_VENTILATION_MODE)
        )
        cooling = ventilation_mode.get(OverkizCommandParam.COOLING)

        if cooling == OverkizCommandParam.ON:
            return FAN_BYPASS

        return OVERKIZ_TO_FAN_MODES[
            cast(str, self.executor.select_state(OverkizState.IO_AIR_DEMAND_MODE))
        ]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode == FAN_BYPASS:
            await self.executor.async_execute_command(
                OverkizCommand.SET_AIR_DEMAND_MODE, OverkizCommandParam.AUTO
            )
            await self._set_ventilation_mode(cooling=OverkizCommandParam.ON)
        else:
            await self._set_ventilation_mode(cooling=OverkizCommandParam.OFF)
            await self.executor.async_execute_command(
                OverkizCommand.SET_AIR_DEMAND_MODE, FAN_MODES_TO_OVERKIZ[fan_mode]
            )

        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_VENTILATION_STATE,
        )

    async def _set_ventilation_mode(
        self,
        cooling: str | None = None,
        prog: str | None = None,
    ) -> None:
        """Execute ventilation mode command with all parameters."""
        ventilation_mode = cast(
            dict, self.executor.select_state(OverkizState.IO_VENTILATION_MODE)
        )

        if cooling:
            ventilation_mode[OverkizCommandParam.COOLING] = cooling

        if prog:
            ventilation_mode[OverkizCommandParam.PROG] = prog

        await self.executor.async_execute_command(
            OverkizCommand.SET_VENTILATION_MODE, ventilation_mode
        )
