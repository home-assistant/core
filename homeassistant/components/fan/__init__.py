"""Provides functionality to interact with fans."""

from __future__ import annotations

from datetime import timedelta
from enum import IntFlag
import functools as ft
import logging
import math
from typing import Any, final

from propcache.api import cached_property
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "fan"
DATA_COMPONENT: HassKey[EntityComponent[FanEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)


class FanEntityFeature(IntFlag):
    """Supported features of the fan entity."""

    SET_SPEED = 1
    OSCILLATE = 2
    DIRECTION = 4
    PRESET_MODE = 8
    TURN_OFF = 16
    TURN_ON = 32


SERVICE_INCREASE_SPEED = "increase_speed"
SERVICE_DECREASE_SPEED = "decrease_speed"
SERVICE_OSCILLATE = "oscillate"
SERVICE_SET_DIRECTION = "set_direction"
SERVICE_SET_PERCENTAGE = "set_percentage"
SERVICE_SET_PRESET_MODE = "set_preset_mode"

DIRECTION_FORWARD = "forward"
DIRECTION_REVERSE = "reverse"

ATTR_PERCENTAGE = "percentage"
ATTR_PERCENTAGE_STEP = "percentage_step"
ATTR_OSCILLATING = "oscillating"
ATTR_DIRECTION = "direction"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"

# mypy: disallow-any-generics


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


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the fans are on based on the statemachine."""
    entity = hass.states.get(entity_id)
    assert entity
    return entity.state == STATE_ON


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Expose fan control via statemachine and services."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[FanEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    # After the transition to percentage and preset_modes concludes,
    # switch this back to async_turn_on and remove async_turn_on_compat
    component.async_register_entity_service(
        SERVICE_TURN_ON,
        {
            vol.Optional(ATTR_PERCENTAGE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional(ATTR_PRESET_MODE): cv.string,
        },
        "async_handle_turn_on_service",
        [FanEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, None, "async_turn_off", [FanEntityFeature.TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [FanEntityFeature.TURN_OFF, FanEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_INCREASE_SPEED,
        {
            vol.Optional(ATTR_PERCENTAGE_STEP): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_increase_speed",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_DECREASE_SPEED,
        {
            vol.Optional(ATTR_PERCENTAGE_STEP): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_decrease_speed",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_OSCILLATE,
        {vol.Required(ATTR_OSCILLATING): cv.boolean},
        "async_oscillate",
        [FanEntityFeature.OSCILLATE],
    )
    component.async_register_entity_service(
        SERVICE_SET_DIRECTION,
        {vol.Optional(ATTR_DIRECTION): cv.string},
        "async_set_direction",
        [FanEntityFeature.DIRECTION],
    )
    component.async_register_entity_service(
        SERVICE_SET_PERCENTAGE,
        {
            vol.Required(ATTR_PERCENTAGE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_percentage",
        [FanEntityFeature.SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        {vol.Required(ATTR_PRESET_MODE): cv.string},
        "async_handle_set_preset_mode_service",
        [FanEntityFeature.SET_SPEED, FanEntityFeature.PRESET_MODE],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


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

    _entity_component_unrecorded_attributes = frozenset({ATTR_PRESET_MODES})

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
    def capability_attributes(self) -> dict[str, list[str] | None]:
        """Return capability attributes."""
        attrs = {}
        supported_features = self.supported_features

        if (
            FanEntityFeature.SET_SPEED in supported_features
            or FanEntityFeature.PRESET_MODE in supported_features
        ):
            attrs[ATTR_PRESET_MODES] = self.preset_modes

        return attrs

    @final
    @property
    def state_attributes(self) -> dict[str, float | str | None]:
        """Return optional state attributes."""
        data: dict[str, float | str | None] = {}
        supported_features = self.supported_features

        if FanEntityFeature.DIRECTION in supported_features:
            data[ATTR_DIRECTION] = self.current_direction

        if FanEntityFeature.OSCILLATE in supported_features:
            data[ATTR_OSCILLATING] = self.oscillating

        has_set_speed = FanEntityFeature.SET_SPEED in supported_features

        if has_set_speed:
            data[ATTR_PERCENTAGE] = self.percentage
            data[ATTR_PERCENTAGE_STEP] = self.percentage_step

        if has_set_speed or FanEntityFeature.PRESET_MODE in supported_features:
            data[ATTR_PRESET_MODE] = self.preset_mode

        return data

    @cached_property
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
