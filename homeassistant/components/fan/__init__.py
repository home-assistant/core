"""Provides functionality to interact with fans."""
from datetime import timedelta
import functools as ft
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.const import SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON
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

SPEED_OFF = "off"
SPEED_LOW = "low"
SPEED_MEDIUM = "medium"
SPEED_HIGH = "high"

DIRECTION_FORWARD = "forward"
DIRECTION_REVERSE = "reverse"

ATTR_SPEED = "speed"
ATTR_SPEED_LIST = "speed_list"
ATTR_OSCILLATING = "oscillating"
ATTR_DIRECTION = "direction"

PROP_TO_ATTR = {
    "speed": ATTR_SPEED,
    "oscillating": ATTR_OSCILLATING,
    "current_direction": ATTR_DIRECTION,
}


@bind_hass
def is_on(hass, entity_id: str) -> bool:
    """Return if the fans are on based on the statemachine."""
    state = hass.states.get(entity_id)
    return state.attributes[ATTR_SPEED] not in [SPEED_OFF, None]


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
        if speed is SPEED_OFF:
            await self.async_turn_off()
        else:
            await self.hass.async_add_job(self.set_speed, speed)

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        raise NotImplementedError()

    async def async_set_direction(self, direction: str):
        """Set the direction of the fan."""
        await self.hass.async_add_job(self.set_direction, direction)

    # pylint: disable=arguments-differ
    def turn_on(self, speed: Optional[str] = None, **kwargs) -> None:
        """Turn on the fan."""
        raise NotImplementedError()

    # pylint: disable=arguments-differ
    async def async_turn_on(self, speed: Optional[str] = None, **kwargs):
        """Turn on the fan."""
        if speed is SPEED_OFF:
            await self.async_turn_off()
        else:
            await self.hass.async_add_job(ft.partial(self.turn_on, speed, **kwargs))

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        pass

    async def async_oscillate(self, oscillating: bool):
        """Oscillate the fan."""
        await self.hass.async_add_job(self.oscillate, oscillating)

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return self.speed not in [SPEED_OFF, None]

    @property
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        return None

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return []

    @property
    def current_direction(self) -> Optional[str]:
        """Return the current direction of the fan."""
        return None

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        return {ATTR_SPEED_LIST: self.speed_list}

    @property
    def state_attributes(self) -> dict:
        """Return optional state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            if not hasattr(self, prop):
                continue

            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0
