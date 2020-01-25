"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_SPEED,
    DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_SPEED,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)


async def async_turn_on(hass, entity_id=ENTITY_MATCH_ALL, speed: str = None) -> None:
    """Turn all or specified fan on."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_SPEED, speed)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL) -> None:
    """Turn all or specified fan off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


async def async_oscillate(
    hass, entity_id=ENTITY_MATCH_ALL, should_oscillate: bool = True
) -> None:
    """Set oscillation on all or specified fan."""
    data = {
        key: value
        for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_OSCILLATING, should_oscillate),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_OSCILLATE, data, blocking=True)


async def async_set_speed(hass, entity_id=ENTITY_MATCH_ALL, speed: str = None) -> None:
    """Set speed for all or specified fan."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_SPEED, speed)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_SPEED, data, blocking=True)


async def async_set_direction(
    hass, entity_id=ENTITY_MATCH_ALL, direction: str = None
) -> None:
    """Set direction for all or specified fan."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_DIRECTION, direction)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_DIRECTION, data, blocking=True)
