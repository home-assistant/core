"""Provides functionality to interact with fans."""
import asyncio
from datetime import timedelta
import functools as ft
import logging
from typing import Callable, List, Optional

import voluptuous as vol

from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import bind_hass
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "fan"
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

# Bitfield of features supported by the fan entity
SUPPORT_SET_SPEED = 1
SUPPORT_OSCILLATE = 2
SUPPORT_DIRECTION = 4

SERVICE_SET_SPEED = "set_speed"
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
ATTR_SPEED_LIST = "speed_list"
ATTR_OSCILLATING = "oscillating"
ATTR_DIRECTION = "direction"
ATTR_PRESET_MODE = "preset_mode"
ATTR_PRESET_MODES = "preset_modes"

# Invalid speeds do not conform to the entity model, but have crept
# into core integrations at some point so we are temporarily
# accommodating them in the transition to percentages.
_NOT_SPEED_OFF = "off"
_NOT_SPEED_AUTO = "auto"
_NOT_SPEED_SMART = "smart"
_NOT_SPEED_INTERVAL = "interval"
_NOT_SPEED_IDLE = "idle"
_NOT_SPEED_FAVORITE = "favorite"

_NOT_SPEEDS_FILTER = {
    _NOT_SPEED_OFF,
    _NOT_SPEED_AUTO,
    _NOT_SPEED_SMART,
    _NOT_SPEED_INTERVAL,
    _NOT_SPEED_IDLE,
    _NOT_SPEED_FAVORITE,
}

_FAN_NATIVE = "_fan_native"

OFF_SPEED_VALUES = [SPEED_OFF, None]

NO_VALID_SPEEDS_EXCEPTION_MESSAGE = "The speed_list contains no valid speeds"


class NoValidSpeedsError(ValueError):
    """Exception class when there are no valid speeds."""


@bind_hass
def is_on(hass, entity_id: str) -> bool:
    """Return if the fans are on based on the statemachine."""
    state = hass.states.get(entity_id)
    if ATTR_SPEED in state.attributes:
        return state.attributes[ATTR_SPEED] not in OFF_SPEED_VALUES
    return state.state == STATE_ON


async def async_setup(hass, config: dict):
    """Expose fan control via statemachine and services."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        {
            vol.Optional(ATTR_SPEED): cv.string,
            vol.Optional(ATTR_PERCENTAGE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        },
        "async_turn_on",
    )
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")
    component.async_register_entity_service(
        SERVICE_SET_SPEED,
        {vol.Required(ATTR_SPEED): cv.string},
        "async_set_speed",
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
        [SUPPORT_SET_SPEED],
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


def _fan_native(method):
    """Native fan method not overridden."""
    setattr(method, _FAN_NATIVE, True)
    return method


class FanEntity(ToggleEntity):
    """Representation of a fan."""

    @_fan_native
    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        raise NotImplementedError()

    @_fan_native
    async def async_set_speed(self, speed: str):
        """Set the speed of the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
        elif not hasattr(self.async_set_percentage, _FAN_NATIVE):
            await self.async_set_percentage(self.speed_to_percentage(speed))
        elif not hasattr(self.set_percentage, _FAN_NATIVE):
            await self.hass.async_add_executor_job(
                self.set_percentage, self.speed_to_percentage(speed)
            )
        else:
            await self.hass.async_add_executor_job(self.set_speed, speed)

    @_fan_native
    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        raise NotImplementedError()

    @_fan_native
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
        elif not hasattr(self.set_percentage, _FAN_NATIVE):
            await self.hass.async_add_executor_job(self.set_percentage, percentage)
        else:
            await self.async_set_speed(self.percentage_to_speed(percentage))

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if not self._implemented_speed and not self._implemented_percentage:
            raise NotImplementedError

        if preset_mode in self.preset_modes:
            self.set_speed(preset_mode)
        else:
            raise ValueError

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if not self._implemented_speed and not self._implemented_percentage:
            raise NotImplementedError

        if preset_mode in self.preset_modes:
            await self.async_set_speed(preset_mode)
        else:
            raise ValueError

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        raise NotImplementedError()

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        await self.hass.async_add_executor_job(self.set_direction, direction)

    # pylint: disable=arguments-differ
    def turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        raise NotImplementedError()

    # pylint: disable=arguments-differ
    async def async_turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
        else:
            speed, percentage, preset_mode = self._convert_legacy_turn_on_arguments(
                speed, percentage, preset_mode
            )
            await self.hass.async_add_executor_job(
                ft.partial(
                    self.turn_on,
                    speed=speed,
                    percentage=percentage,
                    preset_mode=preset_mode,
                    **kwargs,
                )
            )

    def _convert_legacy_turn_on_arguments(self, speed, percentage, preset_mode):
        """Convert turn on arguments for backwards compatibility."""
        if preset_mode is not None:
            speed = preset_mode
            percentage = None
        elif speed is not None:
            if speed in self.preset_modes:
                percentage = None
            else:
                percentage = self.speed_to_percentage(speed)
        elif percentage is not None:
            speed = self.percentage_to_speed(percentage)
        return speed, percentage, preset_mode

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
    def _implemented_percentage(self):
        """Return true if percentage has been implemented."""
        return not hasattr(self.set_percentage, _FAN_NATIVE) or not hasattr(
            self.async_set_percentage, _FAN_NATIVE
        )

    @property
    def _implemented_speed(self):
        """Return true if speed has been implemented."""
        return not hasattr(self.set_speed, _FAN_NATIVE) or not hasattr(
            self.async_set_speed, _FAN_NATIVE
        )

    @property
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        if self._implemented_percentage:
            return self.percentage_to_speed(self.percentage)
        return None

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed as a percentage."""
        if not self._implemented_percentage:
            speed = self.speed
            if speed in self.preset_modes:
                return None
            return self.speed_to_percentage(speed)
        return 0

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        if self._implemented_percentage:
            return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]
        return []

    @property
    def current_direction(self) -> Optional[str]:
        """Return the current direction of the fan."""
        return None

    @property
    def oscillating(self):
        """Return whether or not the fan is currently oscillating."""
        return None

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        if self.supported_features & SUPPORT_SET_SPEED:
            return {
                ATTR_SPEED_LIST: self.speed_list,
                ATTR_PRESET_MODES: self.preset_modes,
            }
        return {}

    def speed_to_percentage(self, speed: str) -> int:
        """
        Map a speed to a percentage.

        Officially this should only have to deal with the 4 pre-defined speeds:

        return {
            SPEED_OFF: 0,
            SPEED_LOW: 33,
            SPEED_MEDIUM: 66,
            SPEED_HIGH: 100,
        }[speed]

        Unfortunately lots of fans make up their own speeds. So the default
        mapping is more dynamic.
        """
        if speed in OFF_SPEED_VALUES:
            return 0

        try:
            return ordered_list_item_to_percentage(
                _filter_out_preset_modes(self.speed_list), speed
            )
        except ValueError as ex:
            raise NoValidSpeedsError(NO_VALID_SPEEDS_EXCEPTION_MESSAGE) from ex

    def percentage_to_speed(self, percentage: int) -> str:
        """
        Map a percentage onto self.speed_list.

        Officially, this should only have to deal with 4 pre-defined speeds.

        if value == 0:
            return SPEED_OFF
        elif value <= 33:
            return SPEED_LOW
        elif value <= 66:
            return SPEED_MEDIUM
        else:
            return SPEED_HIGH

        Unfortunately there is currently a high degree of non-conformancy.
        Until fans have been corrected a more complicated and dynamic
        mapping is used.
        """
        if percentage == 0:
            return SPEED_OFF

        try:
            return percentage_to_ordered_list_item(
                _filter_out_preset_modes(self.speed_list), percentage
            )
        except ValueError as ex:
            raise NoValidSpeedsError(NO_VALID_SPEEDS_EXCEPTION_MESSAGE) from ex

    @property
    def state_attributes(self) -> dict:
        """Return optional state attributes."""
        data = {}
        supported_features = self.supported_features

        if supported_features & SUPPORT_DIRECTION:
            data[ATTR_DIRECTION] = self.current_direction

        if supported_features & SUPPORT_OSCILLATE:
            data[ATTR_OSCILLATING] = self.oscillating

        if supported_features & SUPPORT_SET_SPEED:
            data[ATTR_SPEED] = self.speed
            data[ATTR_PERCENTAGE] = self.percentage
            data[ATTR_PRESET_MODE] = self.preset_mode

        return data

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., auto, smart, interval, favorite.

        Requires SUPPORT_SET_SPEED.
        """
        speed = self.speed
        if speed in self.preset_modes:
            return speed
        return None

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.

        Requires SUPPORT_SET_SPEED.
        """
        return _filter_out_speeds(self.speed_list)


# Decorator
def fan_compat(func: Callable) -> Callable:
    """Compaitiblity for fans that did not implement percentage or preset mode."""

    # Check for partials to properly determine if coroutine function
    check_func = func
    while isinstance(check_func, ft.partial):
        check_func = check_func.func

    if asyncio.iscoroutinefunction(check_func):

        @ft.wraps(func)
        async def wrap_async_turn_on(
            self,
            speed: str = None,
            percentage: int = None,
            preset_mode: Optional[str] = None,
            **kwargs,
        ) -> None:
            """Wrap async_turn_on to add percentage and preset mode compatibility."""
            speed, percentage, preset_mode = self._convert_legacy_turn_on_arguments(
                speed, percentage, preset_mode
            )
            return await check_func(
                self,
                speed=speed,
                percentage=percentage,
                preset_mode=preset_mode,
                **kwargs,
            )

        return wrap_async_turn_on

    @ft.wraps(func)
    def wrap_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Wrap turn_on to add percentage and preset mode compatibility."""
        speed, percentage, preset_mode = self._convert_legacy_turn_on_arguments(
            speed, percentage, preset_mode
        )
        return check_func(
            self, speed=speed, percentage=percentage, preset_mode=preset_mode, **kwargs
        )

    return wrap_turn_on


def _filter_out_preset_modes(speed_list: List):
    """Filter out non-speeds from the speed list.

    The goal is to get the speeds in a list from lowest to
    highest by removing speeds that are not valid or out of order
    so we can map them to percentages.

    Examples:
      input: ["off", "low", "low-medium", "medium", "medium-high", "high", "auto"]
      output: ["low", "low-medium", "medium", "medium-high", "high"]

      input: ["off", "auto", "low", "medium", "high"]
      output: ["low", "medium", "high"]

      input: ["off", "1", "2", "3", "4", "5", "6", "7", "smart"]
      output: ["1", "2", "3", "4", "5", "6", "7"]

      input: ["Auto", "Silent", "Favorite", "Idle", "Medium", "High", "Strong"]
      output: ["Silent", "Medium", "High", "Strong"]
    """

    return [speed for speed in speed_list if speed.lower() not in _NOT_SPEEDS_FILTER]


def _filter_out_speeds(speed_list: List):
    """Filter out non-preset modes from the speed list.

    The goal is to return only preset modes.

    Examples:
      input: ["off", "low", "low-medium", "medium", "medium-high", "high", "auto"]
      output: ["auto"]

      input: ["off", "auto", "low", "medium", "high"]
      output: ["auto"]

      input: ["off", "1", "2", "3", "4", "5", "6", "7", "smart"]
      output: ["smart"]

      input: ["Auto", "Silent", "Favorite", "Idle", "Medium", "High", "Strong"]
      output: ["Auto", "Favorite", "Idle"]
    """

    return [
        speed
        for speed in speed_list
        if speed.lower() in _NOT_SPEEDS_FILTER and speed.lower() != SPEED_OFF
    ]
