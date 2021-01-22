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

INVALID_SPEEDS_FILTER = {"on", "auto", "smart"}

_FAN_NATIVE = "_fan_native"

OFF_SPEED_VALUES = [SPEED_OFF, None]


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

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        raise NotImplementedError()

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        await self.hass.async_add_executor_job(self.set_direction, direction)

    # pylint: disable=arguments-differ
    def turn_on(
        self, speed: Optional[str] = None, percentage: Optional[int] = None, **kwargs
    ) -> None:
        """Turn on the fan."""
        raise NotImplementedError()

    # pylint: disable=arguments-differ
    async def async_turn_on(
        self, speed: Optional[str] = None, percentage: Optional[int] = None, **kwargs
    ) -> None:
        """Turn on the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
        else:
            if percentage is None and speed is not None:
                percentage = self.speed_to_percentage(speed)

            if speed is None and percentage is not None:
                speed = self.percentage_to_speed(percentage)

            await self.hass.async_add_executor_job(
                ft.partial(self.turn_on, speed=speed, percentage=percentage, **kwargs)
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
    def _implemented_percentage(self):
        """Return true if percentage has been implemented."""
        return not hasattr(self.set_percentage, _FAN_NATIVE) or not hasattr(
            self.async_set_percentage, _FAN_NATIVE
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
            return self.speed_to_percentage(self.speed)
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
            return {ATTR_SPEED_LIST: self.speed_list}
        return {}

    def speed_to_percentage(self, speed: str) -> Optional[int]:
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

        normalized_speed_list = self._normalized_speed_list

        if speed not in normalized_speed_list:
            return None

        speeds_len = len(normalized_speed_list)
        speed_offset = normalized_speed_list.index(speed)

        return ((speed_offset) * 100) // (speeds_len - 1)

    @property
    def _normalized_speed_list(self) -> List[str]:
        """Filter out invalid speeds that have crept into fans over time."""
        normalized_speed_list = [
            speed for speed in self.speed_list if speed not in INVALID_SPEEDS_FILTER
        ]
        if normalized_speed_list and normalized_speed_list[0] != SPEED_OFF:
            normalized_speed_list.insert(0, SPEED_OFF)

        return normalized_speed_list

    def percentage_to_speed(self, value: int) -> Optional[str]:
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
        if value == 0:
            return SPEED_OFF

        normalized_speed_list = self._normalized_speed_list
        speeds_len = len(normalized_speed_list)

        if not speeds_len:
            return None

        for offset, speed in enumerate(normalized_speed_list[1:], start=1):
            upper_bound = (offset * 100) // (speeds_len - 1)
            if value <= upper_bound:
                return speed

        return normalized_speed_list[-1]

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

        return data

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0


# Decorator
def percentage_compat(func: Callable) -> Callable:
    """Compaitiblity for fans that expect speed."""

    # Check for partials to properly determine if coroutine function
    check_func = func
    while isinstance(check_func, ft.partial):
        check_func = check_func.func

    if asyncio.iscoroutinefunction(check_func):

        @ft.wraps(func)
        async def wrap_async_turn_on(
            self, speed: str = None, percentage: int = None, **kwargs
        ) -> None:
            """Wrap async_turn_on to add percentage compatibility."""
            if percentage is not None and speed is None:
                speed = self.percentage_to_speed(percentage)

            return await check_func(self, speed=speed, percentage=percentage, **kwargs)

        return wrap_async_turn_on

    @ft.wraps(func)
    async def wrap_turn_on(
        self, speed: str = None, percentage: int = None, **kwargs
    ) -> None:
        """Wrap turn_on to add percentage compatibility."""
        if percentage is not None and speed is None:
            speed = self.percentage_to_speed(percentage)

        return check_func(self, speed=speed, percentage=percentage, **kwargs)

    return wrap_turn_on


# Decorator
def speed_compat(func: Callable) -> Callable:
    """Compaitiblity for fans that expect percentage."""

    # Check for partials to properly determine if coroutine function
    check_func = func
    while isinstance(check_func, ft.partial):
        check_func = check_func.func

    if asyncio.iscoroutinefunction(check_func):

        @ft.wraps(func)
        async def wrap_async_turn_on(
            self, speed: str = None, percentage: int = None, **kwargs
        ) -> None:
            """Wrap async_turn_on to add percentage compatibility."""
            if speed is not None and percentage is None:
                percentage = self.speed_to_percentage(speed)

            return await check_func(self, speed=speed, percentage=percentage, **kwargs)

        return wrap_async_turn_on

    @ft.wraps(func)
    async def wrap_turn_on(
        self, speed: str = None, percentage: int = None, **kwargs
    ) -> None:
        """Wrap turn_on to add percentage compatibility."""
        if speed is not None and percentage is None:
            percentage = self.speed_to_percentage(speed)

        return check_func(self, speed=speed, percentage=percentage, **kwargs)

    return wrap_turn_on
