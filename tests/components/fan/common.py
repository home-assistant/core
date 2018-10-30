"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_SPEED, ATTR_OSCILLATING, DOMAIN,
    SERVICE_OSCILLATE, SERVICE_SET_DIRECTION, SERVICE_SET_SPEED)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF)
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id: str = None, speed: str = None) -> None:
    """Turn all or specified fan on."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_SPEED, speed),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def turn_off(hass, entity_id: str = None) -> None:
    """Turn all or specified fan off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def oscillate(hass, entity_id: str = None,
              should_oscillate: bool = True) -> None:
    """Set oscillation on all or specified fan."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_OSCILLATING, should_oscillate),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_OSCILLATE, data)


@bind_hass
def set_speed(hass, entity_id: str = None, speed: str = None) -> None:
    """Set speed for all or specified fan."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_SPEED, speed),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SET_SPEED, data)


@bind_hass
def set_direction(hass, entity_id: str = None, direction: str = None) -> None:
    """Set direction for all or specified fan."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_DIRECTION, direction),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_SET_DIRECTION, data)
