"""Support for Atlantic Pass APC Heating Control."""
from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

OVERKIZ_TO_HVAC_MODE: dict[str, str] = {
    OverkizCommandParam.AUTO: HVACMode.AUTO,
    OverkizCommandParam.ECO: HVACMode.AUTO,
    OverkizCommandParam.MANU: HVACMode.HEAT,
    OverkizCommandParam.HEATING: HVACMode.HEAT,
    OverkizCommandParam.STOP: HVACMode.OFF,
    OverkizCommandParam.INTERNAL_SCHEDULING: HVACMode.AUTO,
    OverkizCommandParam.COMFORT: HVACMode.HEAT,
}

HVAC_MODE_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_HVAC_MODE.items()}

OVERKIZ_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.OFF: PRESET_ECO,
    OverkizCommandParam.STOP: PRESET_ECO,
    OverkizCommandParam.MANU: PRESET_COMFORT,
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.ABSENCE: PRESET_AWAY,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.INTERNAL_SCHEDULING: PRESET_HOME,
}

PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODES.items()}

OVERKIZ_TO_PROFILE_MODES: dict[str, str] = {
    OverkizCommandParam.OFF: PRESET_SLEEP,
    OverkizCommandParam.STOP: PRESET_SLEEP,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.ABSENCE: PRESET_AWAY,
    OverkizCommandParam.MANU: PRESET_COMFORT,
    OverkizCommandParam.DEROGATION: PRESET_COMFORT,
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
}

OVERKIZ_TEMPERATURE_STATE_BY_PROFILE: dict[str, str] = {
    OverkizCommandParam.ECO: OverkizState.CORE_ECO_HEATING_TARGET_TEMPERATURE,
    OverkizCommandParam.COMFORT: OverkizState.CORE_COMFORT_HEATING_TARGET_TEMPERATURE,
    OverkizCommandParam.DEROGATION: OverkizState.CORE_DEROGATED_TARGET_TEMPERATURE,
}


class AtlanticPassAPCHeatingZone(OverkizEntity, ClimateEntity):
    """Representation of Atlantic Pass APC Heating Zone Control."""

    _attr_hvac_modes = [*HVAC_MODE_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        # Temperature sensor use the same base_device_url and use the n+1 index
        self.temperature_device = self.executor.linked_device(
            int(self.index_device_url) + 1
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if temperature := self.temperature_device.states[OverkizState.CORE_TEMPERATURE]:
            return cast(float, temperature.value)

        return None

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return OVERKIZ_TO_HVAC_MODE[
            cast(str, self.executor.select_state(OverkizState.IO_PASS_APC_HEATING_MODE))
        ]

    @property
    def current_heating_profile(self) -> str:
        """Return current heating profile."""
        return cast(
            str,
            self.executor.select_state(OverkizState.IO_PASS_APC_HEATING_PROFILE),
        )

    async def async_set_heating_mode(self, mode: str) -> None:
        """Set new heating mode and refresh states."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_PASS_APC_HEATING_MODE, mode
        )

        if self.current_heating_profile == OverkizCommandParam.DEROGATION:
            # If current mode is in derogation, disable it
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATION_ON_OFF_STATE, OverkizCommandParam.OFF
            )

        # We also needs to execute these 2 commands to make it work correctly
        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_HEATING_MODE
        )
        await self.executor.async_execute_command(
            OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE
        )

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        await self.async_set_heating_mode(HVAC_MODE_TO_OVERKIZ[hvac_mode])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.async_set_heating_mode(PRESET_MODES_TO_OVERKIZ[preset_mode])

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        heating_mode = cast(
            str, self.executor.select_state(OverkizState.IO_PASS_APC_HEATING_MODE)
        )

        if heating_mode == OverkizCommandParam.INTERNAL_SCHEDULING:
            # In Internal scheduling, it could be comfort or eco
            return OVERKIZ_TO_PROFILE_MODES[
                cast(
                    str,
                    self.executor.select_state(
                        OverkizState.IO_PASS_APC_HEATING_PROFILE
                    ),
                )
            ]

        return OVERKIZ_TO_PRESET_MODES[heating_mode]

    @property
    def target_temperature(self) -> float:
        """Return hvac target temperature."""
        current_heating_profile = self.current_heating_profile
        if current_heating_profile in OVERKIZ_TEMPERATURE_STATE_BY_PROFILE:
            return cast(
                float,
                self.executor.select_state(
                    OVERKIZ_TEMPERATURE_STATE_BY_PROFILE[current_heating_profile]
                ),
            )
        return cast(
            float, self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        if self.hvac_mode == HVACMode.AUTO:
            await self.executor.async_execute_command(
                OverkizCommand.SET_COMFORT_HEATING_TARGET_TEMPERATURE,
                temperature,
            )
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_COMFORT_HEATING_TARGET_TEMPERATURE
            )
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_TARGET_TEMPERATURE
            )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATED_TARGET_TEMPERATURE,
                temperature,
            )
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATION_ON_OFF_STATE,
                OverkizCommandParam.ON,
            )
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_TARGET_TEMPERATURE
            )
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_PASS_APC_HEATING_MODE
            )
            await self.executor.async_execute_command(
                OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE
            )
