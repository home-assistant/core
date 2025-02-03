"""Support for EvoHomeController."""

from datetime import timedelta

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.util import dt as dt_util

from ..entity import OverkizDataUpdateCoordinator, OverkizEntity

PRESET_DAY_OFF = "day-off"
PRESET_HOLIDAYS = "holidays"

OVERKIZ_TO_HVAC_MODES: dict[str, HVACMode] = {
    OverkizCommandParam.AUTO: HVACMode.AUTO,
    OverkizCommandParam.OFF: HVACMode.OFF,
}
HVAC_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODES.items()}

OVERKIZ_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.DAY_OFF: PRESET_DAY_OFF,
    OverkizCommandParam.HOLIDAYS: PRESET_HOLIDAYS,
}
PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODES.items()}


class EvoHomeController(OverkizEntity, ClimateEntity):
    """Representation of EvoHomeController device."""

    _attr_hvac_modes = [*HVAC_MODES_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        if self._attr_device_info:
            self._attr_device_info["manufacturer"] = "EvoHome"

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if state := self.device.states.get(OverkizState.RAMSES_RAMSES_OPERATING_MODE):
            operating_mode = state.value_as_str

            if operating_mode in OVERKIZ_TO_HVAC_MODES:
                return OVERKIZ_TO_HVAC_MODES[operating_mode]

            if operating_mode in OVERKIZ_TO_PRESET_MODES:
                return HVACMode.OFF

        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_OPERATING_MODE, HVAC_MODES_TO_OVERKIZ[hvac_mode]
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        if (
            state := self.device.states[OverkizState.RAMSES_RAMSES_OPERATING_MODE]
        ) and state.value_as_str in OVERKIZ_TO_PRESET_MODES:
            return OVERKIZ_TO_PRESET_MODES[state.value_as_str]

        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_DAY_OFF:
            today_end_of_day = dt_util.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            time_interval = today_end_of_day

        if preset_mode == PRESET_HOLIDAYS:
            one_week_from_now = dt_util.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=7)
            time_interval = one_week_from_now

        await self.executor.async_execute_command(
            OverkizCommand.SET_OPERATING_MODE,
            PRESET_MODES_TO_OVERKIZ[preset_mode],
            time_interval.strftime("%Y/%m/%d %H:%M"),
        )
