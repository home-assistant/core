"""Support for EvoHome HeatingSetPoint."""

from __future__ import annotations

from typing import Any, cast

from pyoverkiz.enums import OverkizAttribute, OverkizCommand, OverkizState
from pyoverkiz.models import State

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from ..const import OVERKIZ_UNIT_TO_HA
from ..entity import OverkizDataUpdateCoordinator, OverkizEntity


class HeatingSetPoint(OverkizEntity, ClimateEntity):
    """Representation of EvoHome HeatingSetPoint device."""

    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 0.5

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        if (
            self.device.attributes
            and OverkizAttribute.CORE_MEASURED_VALUE_TYPE in self.device.attributes
        ):
            attribute = cast(
                State, self.device.attributes[OverkizAttribute.CORE_MEASURED_VALUE_TYPE]
            )

            self._attr_temperature_unit = OVERKIZ_UNIT_TO_HA[attribute.value_as_str]
        else:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        self._attr_min_temp = cast(
            State, self.device.attributes[OverkizAttribute.CORE_MIN_SETTABLE_VALUE]
        ).value_as_float
        self._attr_max_temp = cast(
            State, self.device.attributes[OverkizAttribute.CORE_MAX_SETTABLE_VALUE]
        ).value_as_float

        if self._attr_device_info:
            self._attr_device_info["manufacturer"] = "EvoHome"

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        current_temperature = self.device.states[OverkizState.CORE_TEMPERATURE]

        if current_temperature:
            return current_temperature.value_as_float

        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        target_temperature = self.device.states[OverkizState.CORE_TARGET_TEMPERATURE]

        if target_temperature:
            return target_temperature.value_as_float

        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = cast(float, kwargs.get(ATTR_TEMPERATURE))

        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, temperature
        )
