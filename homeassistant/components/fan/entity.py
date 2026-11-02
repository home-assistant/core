"""Base entity for the Fan platform."""

import functools as ft
import math
from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    DOMAIN,
    FanEntityCapabilityAttribute,
    FanEntityFeature,
    FanEntityStateAttribute,
)


class NotValidPresetModeError(ServiceValidationError):
    """Raised when the preset_mode is not in the preset_modes list."""

    def __init__(
        self, *args: object, translation_placeholders: dict[str, str] | None = None
    ) -> None:
        """Initialize the exception."""
        super().__init__(
            *args,
            translation_domain=DOMAIN,
            translation_key="not_valid_preset_mode",
            translation_placeholders=translation_placeholders,
        )


class FanEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes fan entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "percentage",
    "speed_count",
    "current_direction",
    "oscillating",
    "supported_features",
    "preset_mode",
    "preset_modes",
}


class FanEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for fan entities."""

    _entity_component_unrecorded_attributes = frozenset(
        {FanEntityCapabilityAttribute.PRESET_MODES}
    )

    entity_description: FanEntityDescription
    _attr_current_direction: str | None = None
    _attr_oscillating: bool | None = None
    _attr_percentage: int | None = 0
    _attr_preset_mode: str | None = None
    _attr_preset_modes: list[str] | None = None
    _attr_speed_count: int = 100
    _attr_supported_features: FanEntityFeature = FanEntityFeature(0)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        raise NotImplementedError

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
        await self.hass.async_add_executor_job(self.set_percentage, percentage)

    async def async_increase_speed(self, percentage_step: int | None = None) -> None:
        """Increase the speed of the fan."""
        await self._async_adjust_speed(1, percentage_step)

    async def async_decrease_speed(self, percentage_step: int | None = None) -> None:
        """Decrease the speed of the fan."""
        await self._async_adjust_speed(-1, percentage_step)

    async def _async_adjust_speed(
        self, modifier: int, percentage_step: int | None
    ) -> None:
        """Increase or decrease the speed of the fan."""
        current_percentage = self.percentage or 0

        if percentage_step is not None:
            new_percentage = current_percentage + (percentage_step * modifier)
        else:
            speed_range = (1, self.speed_count)
            speed_index = math.ceil(
                percentage_to_ranged_value(speed_range, current_percentage)
            )
            new_percentage = ranged_value_to_percentage(
                speed_range, speed_index + modifier
            )

        new_percentage = max(0, min(100, new_percentage))

        await self.async_set_percentage(new_percentage)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        raise NotImplementedError

    @final
    async def async_handle_set_preset_mode_service(self, preset_mode: str) -> None:
        """Validate and set new preset mode."""
        self._valid_preset_mode_or_raise(preset_mode)
        await self.async_set_preset_mode(preset_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)

    @final
    @callback
    def _valid_preset_mode_or_raise(self, preset_mode: str) -> None:
        """Raise NotValidPresetModeError on invalid preset_mode."""
        preset_modes = self.preset_modes
        if not preset_modes or preset_mode not in preset_modes:
            preset_modes_str: str = ", ".join(preset_modes or [])
            raise NotValidPresetModeError(
                translation_placeholders={
                    "preset_mode": preset_mode,
                    "preset_modes": preset_modes_str,
                },
            )

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        raise NotImplementedError

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self.hass.async_add_executor_job(self.set_direction, direction)

    @override
    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        raise NotImplementedError

    @final
    async def async_handle_turn_on_service(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Validate and turn on the fan."""
        if preset_mode is not None:
            self._valid_preset_mode_or_raise(preset_mode)
        await self.async_turn_on(percentage, preset_mode, **kwargs)

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self.hass.async_add_executor_job(
            ft.partial(
                self.turn_on,
                percentage=percentage,
                preset_mode=preset_mode,
                **kwargs,
            )
        )

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        raise NotImplementedError

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self.hass.async_add_executor_job(self.oscillate, oscillating)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        return (
            self.percentage is not None and self.percentage > 0
        ) or self.preset_mode is not None

    @cached_property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        return self._attr_percentage

    @cached_property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._attr_speed_count

    @property
    def percentage_step(self) -> float:
        """Return the step size for percentage."""
        return 100 / self.speed_count

    @cached_property
    def current_direction(self) -> str | None:
        """Return the current direction of the fan."""
        return self._attr_current_direction

    @cached_property
    def oscillating(self) -> bool | None:
        """Return whether or not the fan is currently oscillating."""
        return self._attr_oscillating

    @property
    @override
    def capability_attributes(self) -> dict[str, list[str] | None]:
        """Return capability attributes."""
        attrs: dict[str, list[str] | None] = {}
        supported_features = self.supported_features

        if (
            FanEntityFeature.SET_SPEED in supported_features
            or FanEntityFeature.PRESET_MODE in supported_features
        ):
            attrs[FanEntityCapabilityAttribute.PRESET_MODES] = self.preset_modes

        return attrs

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return optional state attributes."""
        data: dict[str, float | str | None] = {}
        supported_features = self.supported_features

        if FanEntityFeature.DIRECTION in supported_features:
            data[FanEntityStateAttribute.DIRECTION] = self.current_direction

        if FanEntityFeature.OSCILLATE in supported_features:
            data[FanEntityStateAttribute.OSCILLATING] = self.oscillating

        has_set_speed = FanEntityFeature.SET_SPEED in supported_features

        if has_set_speed:
            data[FanEntityStateAttribute.PERCENTAGE] = self.percentage
            data[FanEntityStateAttribute.PERCENTAGE_STEP] = self.percentage_step

        if has_set_speed or FanEntityFeature.PRESET_MODE in supported_features:
            data[FanEntityStateAttribute.PRESET_MODE] = self.preset_mode

        return data

    @cached_property
    @override
    def supported_features(self) -> FanEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @cached_property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite.

        Requires FanEntityFeature.SET_SPEED.
        """
        return self._attr_preset_mode

    @cached_property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires FanEntityFeature.SET_SPEED.
        """
        return self._attr_preset_modes
