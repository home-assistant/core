"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.automation import DOMAIN, SERVICE_TRIGGER
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE,
    SERVICE_RELOAD)
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id=None):
    """Turn on specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def turn_off(hass, entity_id=None):
    """Turn off specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def toggle(hass, entity_id=None):
    """Toggle specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


@bind_hass
def trigger(hass, entity_id=None):
    """Trigger specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TRIGGER, data)


@bind_hass
def reload(hass):
    """Reload the automation from config."""
    hass.services.call(DOMAIN, SERVICE_RELOAD)


@bind_hass
def async_reload(hass):
    """Reload the automation from config.

    Returns a coroutine object.
    """
    return hass.services.async_call(DOMAIN, SERVICE_RELOAD)
