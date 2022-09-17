"""Support for Atlantic Pass APC Heating And Cooling Zone Control."""
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from ..entity import OverkizEntity

PRESET_FROST_PROTECTION = "frost_protection"

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
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.MANU: PRESET_COMFORT,
    OverkizCommandParam.ABSENCE: PRESET_AWAY,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.INTERNAL_SCHEDULING: PRESET_COMFORT,
}

PRESET_MODES_TO_OVERKIZ = {v: k for k, v in OVERKIZ_TO_PRESET_MODES.items()}

THERMAL_CONFIGURATION_STATE = "core:ThermalConfigurationState"


class AtlanticPassAPCHeatingAndCoolingZone(OverkizEntity, ClimateEntity):
    """Representation of Atlantic Pass APC Heating And Cooling Zone Zone Control."""

    _attr_hvac_modes = [*HVAC_MODE_TO_OVERKIZ]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return OVERKIZ_TO_HVAC_MODE[
            cast(str, self.executor.select_state(OverkizState.IO_PASS_APC_HEATING_MODE))
        ]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        commands = [
            Command(
                OverkizCommand.SET_PASS_APC_HEATING_MODE,
                [HVAC_MODE_TO_OVERKIZ[hvac_mode]],
            ),
            # We also needs to execute these 3 commands to make it work correctly
            Command(
                OverkizCommand.SET_DEROGATION_ON_OFF_STATE,
                [OverkizCommandParam.OFF],
            ),
            Command(OverkizCommand.REFRESH_PASS_APC_HEATING_MODE),
            Command(OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE),
        ]
        await self.executor.async_execute_commands(commands)

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        return OVERKIZ_TO_PRESET_MODES[
            cast(str, self.executor.select_state(OverkizState.IO_PASS_APC_HEATING_MODE))
        ]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        commands = [
            Command(
                OverkizCommand.SET_PASS_APC_HEATING_MODE,
                [PRESET_MODES_TO_OVERKIZ[preset_mode]],
            ),
            # We also needs to execute these 3 commands to make it work correctly
            Command(
                OverkizCommand.SET_DEROGATION_ON_OFF_STATE,
                [OverkizCommandParam.OFF],
            ),
            Command(OverkizCommand.REFRESH_PASS_APC_HEATING_MODE),
            Command(OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE),
        ]

        await self.executor.async_execute_commands(commands)

    @property
    def hvac_action(self) -> str:
        """Return hvac current action."""
        return OVERKIZ_TO_HVAC_MODE[
            cast(str, self.executor.select_state(THERMAL_CONFIGURATION_STATE))
        ]

    @property
    def target_temperature(self) -> float:
        """Return hvac target temperature."""
        return cast(
            float, self.executor.select_state(OverkizState.CORE_TARGET_TEMPERATURE)
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]

        # This might need more test and conditions here
        if self.hvac_mode == HVACMode.AUTO:
            await self.executor.async_execute_command(
                OverkizCommand.SET_DEROGATED_TARGET_TEMPERATURE, temperature
            )
        else:
            await self.executor.async_execute_command(
                OverkizCommand.SET_COMFORT_HEATING_TARGET_TEMPERATURE, temperature
            )
