"""Support for ValveHeatingTemperatureInterface."""
from __future__ import annotations

from typing import Any, cast

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
    UnitOfTemperature,
)
from homeassistant.const import ATTR_TEMPERATURE

from ..const import DOMAIN
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

PRESET_MANUAL = "manual"
PRESET_FROST_PROTECTION = "frost_protection"

OVERKIZ_TO_HVAC_ACTION: dict[str, HVACAction] = {
    OverkizCommandParam.OPEN: HVACAction.HEATING,
    OverkizCommandParam.CLOSED: HVACAction.IDLE,
}

OVERKIZ_TO_PRESET_MODE: dict[str, str] = {
    OverkizCommandParam.GEOFENCING_MODE: PRESET_NONE,
    OverkizCommandParam.SUDDEN_DROP_MODE: PRESET_NONE,
    OverkizCommandParam.AWAY: PRESET_AWAY,
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.FROSTPROTECTION: PRESET_FROST_PROTECTION,
    OverkizCommandParam.MANUAL: PRESET_MANUAL,
}
PRESET_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODE.items()}

TEMPERATURE_SENSOR_DEVICE_INDEX = 2


class ValveHeatingTemperatureInterface(OverkizEntity, ClimateEntity):
    """Representation of Valve Heating Temperature Interface device."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_preset_modes = [*PRESET_MODE_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    )
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

        self._attr_min_temp = cast(
            float, self.executor.select_state(OverkizState.CORE_MIN_SETPOINT)
        )
        self._attr_max_temp = cast(
            float, self.executor.select_state(OverkizState.CORE_MAX_SETPOINT)
        )

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        return OVERKIZ_TO_HVAC_ACTION[
            cast(str, self.executor.select_state(OverkizState.CORE_OPEN_CLOSED_VALVE))
        ]

    @property
    def target_temperature(self) -> float:
        """Return the temperature."""
        return cast(
            float, self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)
        )

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
            OverkizCommand.SET_DEROGATION,
            float(temperature),
            OverkizCommandParam.FURTHER_NOTICE,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        return

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        return OVERKIZ_TO_PRESET_MODE[
            cast(
                str, self.executor.select_state(OverkizState.IO_DEROGATION_HEATING_MODE)
            )
        ]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

        # If we want to switch to manual mode via a preset, we need to pass in a temperature
        # Manual mode will be on automatically if an user sets a temperature
        if preset_mode == PRESET_MANUAL:
            if current_temperature := self.current_temperature:
                await self.executor.async_execute_command(
                    OverkizCommand.SET_DEROGATION,
                    current_temperature,
                    OverkizCommandParam.FURTHER_NOTICE,
                )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATION,
                PRESET_MODE_TO_OVERKIZ[preset_mode],
                OverkizCommandParam.FURTHER_NOTICE,
            )
