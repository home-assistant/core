"""Provides functionality to interact with fans."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import functools as ft
import logging
import math
from typing import final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "fan"
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

# Bitfield of features supported by the fan entity
SUPPORT_SET_SPEED = 1
SUPPORT_OSCILLATE = 2
SUPPORT_DIRECTION = 4
SUPPORT_PRESET_MODE = 8

SERVICE_SET_SPEED = "set_speed"
SERVICE_INCREASE_SPEED = "increase_speed"
SERVICE_DECREASE_SPEED = "decrease_speed"
SERVICE_OSCILLATE = "oscillate"
SERVICE_SET_DIRECTION = "set_direction"
SERVICE_SET_PERCENTAGE = "set_percentage"
SERVICE_SET_PRESET_MODE = "set_preset_mode"

SPEED_OFF = "off"
SPEED_LOW = "low"
SPEED_MEDIUM = "medium"
SPEED_HIGH = "high"

DIRECTION_FORWARD = "forward"
DIRECTION_REVERSE = "reverse"

ATTR_SPEED = "speed"
ATTR_PERCENTAGE = "percentage"
ATTR_PERCENTAGE_STEP = "percentage_step"
ATTR_SPEED_LIST = "speed_list"
ATTR_OSCILLATING = "oscillating"
ATTR_DIRECTION = "direction"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"

_NOT_SPEED_OFF = "off"

OFF_SPEED_VALUES = [SPEED_OFF, None]

LEGACY_SPEED_LIST = [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]


class NoValidSpeedsError(ValueError):
    """Exception class when there are no valid speeds."""


class NotValidSpeedError(ValueError):
    """Exception class when the speed in not in the speed list."""


class NotValidPresetModeError(ValueError):
    """Exception class when the preset_mode in not in the preset_modes list."""


@bind_hass
def is_on(hass, entity_id: str) -> bool:
    """Return if the fans are on based on the statemachine."""
    state = hass.states.get(entity_id)
    if ATTR_SPEED in state.attributes:
        return state.attributes[ATTR_SPEED] not in OFF_SPEED_VALUES
    return state.state == STATE_ON


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Expose fan control via statemachine and services."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    # After the transition to percentage and preset_modes concludes,
    # switch this back to async_turn_on and remove async_turn_on_compat
    component.async_register_entity_service(
        SERVICE_TURN_ON,
        {
            vol.Optional(ATTR_SPEED): cv.string,
            vol.Optional(ATTR_PERCENTAGE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional(ATTR_PRESET_MODE): cv.string,
        },
        "async_turn_on_compat",
    )
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")
    # After the transition to percentage and preset_modes concludes,
    # remove this service
    component.async_register_entity_service(
        SERVICE_SET_SPEED,
        {vol.Required(ATTR_SPEED): cv.string},
        "async_set_speed_deprecated",
        [SUPPORT_SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_INCREASE_SPEED,
        {
            vol.Optional(ATTR_PERCENTAGE_STEP): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_increase_speed",
        [SUPPORT_SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_DECREASE_SPEED,
        {
            vol.Optional(ATTR_PERCENTAGE_STEP): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_decrease_speed",
        [SUPPORT_SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_OSCILLATE,
        {vol.Required(ATTR_OSCILLATING): cv.boolean},
        "async_oscillate",
        [SUPPORT_OSCILLATE],
    )
    component.async_register_entity_service(
        SERVICE_SET_DIRECTION,
        {vol.Optional(ATTR_DIRECTION): cv.string},
        "async_set_direction",
        [SUPPORT_DIRECTION],
    )
    component.async_register_entity_service(
        SERVICE_SET_PERCENTAGE,
        {
            vol.Required(ATTR_PERCENTAGE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_percentage",
        [SUPPORT_SET_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        {vol.Required(ATTR_PRESET_MODE): cv.string},
        "async_set_preset_mode",
        [SUPPORT_SET_SPEED, SUPPORT_PRESET_MODE],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


@dataclass
class FanEntityDescription(ToggleEntityDescription):
    """A class that describes fan entities."""


class FanEntity(ToggleEntity):
    """Base class for fan entities."""

    entity_description: FanEntityDescription
    _attr_current_direction: str | None = None
    _attr_oscillating: bool | None = None
    _attr_percentage: int | None
    _attr_preset_mode: str | None
    _attr_preset_modes: list[str] | None
    _attr_speed_count: int
    _attr_supported_features: int = 0

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        raise NotImplementedError()

    async def async_set_speed_deprecated(self, speed: str):
        """Set the speed of the fan."""
        _LOGGER.error(
            "The fan.set_speed service is deprecated and will fail in 2022.3 and later, use fan.set_percentage or fan.set_preset_mode instead"
        )
        await self.async_set_speed(speed)

    async def async_set_speed(self, speed: str):
        """Set the speed of the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
            return

        if self.preset_modes and speed in self.preset_modes:
            await self.async_set_preset_mode(speed)
            return

        await self.async_set_percentage(self.speed_to_percentage(speed))

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        raise NotImplementedError()

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
        raise NotImplementedError()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)

    def _valid_preset_mode_or_raise(self, preset_mode):
        """Raise NotValidPresetModeError on invalid preset_mode."""
        preset_modes = self.preset_modes
        if not preset_modes or preset_mode not in preset_modes:
            raise NotValidPresetModeError(
                f"The preset_mode {preset_mode} is not a valid preset_mode: {preset_modes}"
            )

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        raise NotImplementedError()

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        await self.hass.async_add_executor_job(self.set_direction, direction)

    # pylint: disable=arguments-differ
    def turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        raise NotImplementedError()

    async def async_turn_on_compat(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn on the fan.

        This _compat version wraps async_turn_on with
        backwards and forward compatibility.

        This compatibility shim will be removed in 2022.3
        """
        if preset_mode is not None:
            self._valid_preset_mode_or_raise(preset_mode)
            speed = preset_mode
            percentage = None
        elif speed is not None:
            _LOGGER.error(
                "Calling fan.turn_on with the speed argument is deprecated and will fail in 2022.3 and later, use percentage or preset_mode instead"
            )
            if self.preset_modes and speed in self.preset_modes:
                preset_mode = speed
                percentage = None
            else:
                percentage = self.speed_to_percentage(speed)
        elif percentage is not None:
            speed = self.percentage_to_speed(percentage)

        await self.async_turn_on(
            speed=speed,
            percentage=percentage,
            preset_mode=preset_mode,
            **kwargs,
        )

    # pylint: disable=arguments-differ
    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
        else:
            await self.hass.async_add_executor_job(
                ft.partial(
                    self.turn_on,
                    speed=speed,
                    percentage=percentage,
                    preset_mode=preset_mode,
                    **kwargs,
                )
            )

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        raise NotImplementedError()

    async def async_oscillate(self, oscillating: bool):
        """Oscillate the fan."""
        await self.hass.async_add_executor_job(self.oscillate, oscillating)

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return self.speed not in [SPEED_OFF, None]

    @property
    def speed(self) -> str | None:
        """Return the current speed."""
        if preset_mode := self.preset_mode:
            return preset_mode
        if (percentage := self.percentage) is None:
            return None
        return self.percentage_to_speed(percentage)

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        if hasattr(self, "_attr_percentage"):
            return self._attr_percentage
        return 0

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if hasattr(self, "_attr_speed_count"):
            return self._attr_speed_count
        return 100

    @property
    def percentage_step(self) -> float:
        """Return the step size for percentage."""
        return 100 / self.speed_count

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        speeds = [SPEED_OFF, *LEGACY_SPEED_LIST]
        if preset_modes := self.preset_modes:
            speeds.extend(preset_modes)
        return speeds

    @property
    def current_direction(self) -> str | None:
        """Return the current direction of the fan."""
        return self._attr_current_direction

    @property
    def oscillating(self) -> bool | None:
        """Return whether or not the fan is currently oscillating."""
        return self._attr_oscillating

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        attrs = {}
        if self.supported_features & SUPPORT_SET_SPEED:
            attrs[ATTR_SPEED_LIST] = self.speed_list

        if (
            self.supported_features & SUPPORT_SET_SPEED
            or self.supported_features & SUPPORT_PRESET_MODE
        ):
            attrs[ATTR_PRESET_MODES] = self.preset_modes

        return attrs

    def speed_to_percentage(self, speed: str) -> int:  # pylint: disable=no-self-use
        """Map a legacy speed to a percentage."""
        if speed in OFF_SPEED_VALUES:
            return 0
        if speed not in LEGACY_SPEED_LIST:
            raise NotValidSpeedError(f"The speed {speed} is not a valid speed.")
        return ordered_list_item_to_percentage(LEGACY_SPEED_LIST, speed)

    def percentage_to_speed(  # pylint: disable=no-self-use
        self, percentage: int
    ) -> str:
        """Map a percentage to a legacy speed."""
        if percentage == 0:
            return SPEED_OFF
        return percentage_to_ordered_list_item(LEGACY_SPEED_LIST, percentage)

    @final
    @property
    def state_attributes(self) -> dict:
        """Return optional state attributes."""
        data: dict[str, float | str | None] = {}
        supported_features = self.supported_features

        if supported_features & SUPPORT_DIRECTION:
            data[ATTR_DIRECTION] = self.current_direction

        if supported_features & SUPPORT_OSCILLATE:
            data[ATTR_OSCILLATING] = self.oscillating

        if supported_features & SUPPORT_SET_SPEED:
            data[ATTR_SPEED] = self.speed
            data[ATTR_PERCENTAGE] = self.percentage
            data[ATTR_PERCENTAGE_STEP] = self.percentage_step

        if (
            supported_features & SUPPORT_PRESET_MODE
            or supported_features & SUPPORT_SET_SPEED
        ):
            data[ATTR_PRESET_MODE] = self.preset_mode

        return data

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite.

        Requires SUPPORT_SET_SPEED.
        """
        if hasattr(self, "_attr_preset_mode"):
            return self._attr_preset_mode
        return None

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires SUPPORT_SET_SPEED.
        """
        if hasattr(self, "_attr_preset_modes"):
            return self._attr_preset_modes
        return None
