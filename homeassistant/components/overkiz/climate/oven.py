"""Support for Overkiz ovens (ogp:Oven / DynamicOven)."""

from typing import Any, cast, override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..entity import OverkizEntity

# Absolute fallbacks, only used when the oven does not report its
# current (mode dependent) target-temperature bounds.
DEFAULT_MIN_TEMP = 35.0
DEFAULT_MAX_TEMP = 275.0


class Oven(OverkizEntity, ClimateEntity):
    """Representation of an Overkiz oven.

    The oven exposes a start/stop actuator, a mode-dependent target
    temperature (with reported lower/upper bounds) and a list of cooking
    modes. It does not report a live cavity temperature, so
    ``current_temperature`` is intentionally not provided.
    """

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if (
            self.device.states.get_value(OverkizState.CORE_STARTED_STOPPED)
            == OverkizCommandParam.STARTED
        ):
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    @override
    def hvac_action(self) -> HVACAction:
        """Return the current running action."""
        if self.hvac_mode != HVACMode.HEAT:
            return HVACAction.OFF
        # Once the set temperature is reached the oven holds it.
        if self.device.states.get_value(OverkizState.CORE_TARGET_TEMPERATURE_REACHED):
            return HVACAction.IDLE
        return HVACAction.HEATING

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return the temperature the oven is set to reach."""
        return cast(
            float | None,
            self.device.states.get_value(OverkizState.CORE_TARGET_TEMPERATURE),
        )

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum settable temperature for the current mode."""
        if (
            value := self.device.states.get_value(
                OverkizState.CORE_TARGET_TEMPERATURE_CURRENT_LOWER_BOUND
            )
        ) is not None:
            return cast(float, value)
        return DEFAULT_MIN_TEMP

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum settable temperature for the current mode."""
        if (
            value := self.device.states.get_value(
                OverkizState.CORE_TARGET_TEMPERATURE_CURRENT_UPPER_BOUND
            )
        ) is not None:
            return cast(float, value)
        return DEFAULT_MAX_TEMP

    @property
    @override
    def preset_modes(self) -> list[str] | None:
        """Return the list of available cooking modes."""
        if modes := self.device.states.get_value(OverkizState.CORE_AVAILABLE_MODES):
            return cast(list[str], modes)
        return None

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current cooking mode."""
        return cast(str | None, self.device.states.get_value(OverkizState.CORE_MODE))

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, temperature
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a new cooking mode."""
        await self.executor.async_execute_command(OverkizCommand.SET_MODE, preset_mode)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Start or stop the oven."""
        if hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    @override
    async def async_turn_on(self) -> None:
        """Start the oven."""
        await self.executor.async_execute_command(OverkizCommand.START)

    @override
    async def async_turn_off(self) -> None:
        """Stop the oven."""
        await self.executor.async_execute_command(OverkizCommand.STOP)
