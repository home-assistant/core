"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified switch on."""
    hass.add_job(async_turn_on, hass, entity_id)


async def async_turn_on(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified switch on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


@bind_hass
def turn_off(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified switch off."""
    hass.add_job(async_turn_off, hass, entity_id)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified switch off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)
