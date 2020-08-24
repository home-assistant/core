"""Provides functionality to interact with fans."""
from datetime import timedelta
import functools as ft
import logging
from typing import Optional

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
SUPPORT_SET_SPEED_PERCENTAGE = 8

SERVICE_SET_SPEED = "set_speed"
SERVICE_OSCILLATE = "oscillate"
SERVICE_SET_DIRECTION = "set_direction"
SERVICE_SET_SPEED_PERCENTAGE = "set_speed_percentage"

SPEED_OFF = "off"
SPEED_LOW = "low"
SPEED_MEDIUM = "medium"
SPEED_HIGH = "high"

DIRECTION_FORWARD = "forward"
DIRECTION_REVERSE = "reverse"

ATTR_SPEED = "speed"
ATTR_SPEED_PERCENTAGE = "speed_percentage"
ATTR_SPEED_LIST = "speed_list"
ATTR_OSCILLATING = "oscillating"
ATTR_DIRECTION = "direction"


@bind_hass
def is_on(hass, entity_id: str) -> bool:
    """Return if the fans are on based on the statemachine."""
    state = hass.states.get(entity_id)
    if ATTR_SPEED in state.attributes:
        return state.attributes[ATTR_SPEED] not in [SPEED_OFF, None]
    return state.state == STATE_ON


async def async_setup(hass, config: dict):
    """Expose fan control via statemachine and services."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON, {vol.Optional(ATTR_SPEED): cv.string}, "async_turn_on"
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
        SERVICE_SET_SPEED_PERCENTAGE,
        {vol.Required(ATTR_SPEED): vol.Number()},
        "async_set_speed_percentage",
        [SUPPORT_SET_SPEED],
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class FanEntity(ToggleEntity):
    """Representation of a fan."""

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        raise NotImplementedError()

    async def async_set_speed(self, speed: str):
        """Set the speed of the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
        elif self.supported_features & SUPPORT_SET_SPEED_PERCENTAGE:
            await self.async_set_speed_percentage(self.speed_to_percentage(speed))
        else:
            await self.hass.async_add_job(self.set_speed, speed)

    def set_speed_percentage(self, speed: str) -> None:
        """Set the speed of the fan, as a percentage."""
        raise NotImplementedError()

    async def async_set_speed_percentage(self, speed: int):
        """Set the speed of the fan, as a percentage."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
        elif not self.supported_features & SUPPORT_SET_SPEED_PERCENTAGE:
            await self.async_set_speed(self.percentage_to_speed(speed))
        else:
            await self.hass.async_add_executor_job(self.set_speed, speed)

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        raise NotImplementedError()

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        await self.hass.async_add_executor_job(self.set_direction, direction)

    # pylint: disable=arguments-differ
    def turn_on(self, speed: Optional[str] = None, **kwargs) -> None:
        """Turn on the fan."""
        raise NotImplementedError()

    # pylint: disable=arguments-differ
    async def async_turn_on(self, speed: Optional[str] = None, **kwargs):
        """Turn on the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
        else:
            await self.hass.async_add_executor_job(
                ft.partial(self.turn_on, speed, **kwargs)
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
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        if self.supported_features & SUPPORT_SET_SPEED_PERCENTAGE:
            return self.percentage_to_speed(self.percentage_speed)
        return None

    @property
    def percentage_speed(self):
        """Return the current speed as a percentage."""
        if not self.supported_features & SUPPORT_SET_SPEED_PERCENTAGE:
            return self.speed_to_percentage(self.speed)
        return None

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        if self.supported_features & SUPPORT_SET_SPEED_PERCENTAGE:
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

    def speed_to_percentage(self, speed: str):
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
        if speed == SPEED_OFF:
            return 0

        speeds_len = len(self.speed_list)
        speed_offset = self.speed_list.index(speed)

        return ((speed_offset) * 100) // ((speeds_len - 1))

    def percentage_to_speed(self, value: int):
        """
        Map a percentage onto self.speed_list

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

        speeds_len = len(self.speed_list)

        for offset, speed in enumerate(self.speed_list[1:], start=1):
            upper_bound = (offset * 100) // ((speeds_len - 1))
            if value <= upper_bound:
                return speed

        return self.speed_list[-1]

    @property
    def state_attributes(self) -> dict:
        """Return optional state attributes."""
        data = {}
        supported_features = self.supported_features

        if supported_features & SUPPORT_DIRECTION:
            data[ATTR_DIRECTION] = self.current_direction

        if supported_features & SUPPORT_OSCILLATE:
            data[ATTR_OSCILLATING] = self.oscillating

        if supported_features & SUPPORT_SET_SPEED or supported_features & SUPPORT_SET_SPEED_PERCENTAGE:
            data[ATTR_SPEED] = self.speed
            data[ATTR_SPEED_PERCENTAGE] = self.percentage_speed

        return data

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0
