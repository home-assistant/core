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
async def async_turn_on(hass, entity_id=None):
    """Turn on specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
async def async_turn_off(hass, entity_id=None):
    """Turn off specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
async def async_toggle(hass, entity_id=None):
    """Toggle specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TOGGLE, data)


@bind_hass
async def async_trigger(hass, entity_id=None):
    """Trigger specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TRIGGER, data)


@bind_hass
async def async_reload(hass):
    """Reload the automation from config."""
    await hass.services.async_call(DOMAIN, SERVICE_RELOAD)
