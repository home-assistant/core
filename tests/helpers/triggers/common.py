"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.automation import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.loader import bind_hass


@bind_hass
async def async_turn_on(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn on specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn off specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data)
