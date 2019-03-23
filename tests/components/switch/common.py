"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.core import callback
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id=None):
    """Turn all or specified switch on."""
    hass.add_job(async_turn_on, hass, entity_id)


@callback
@bind_hass
def async_turn_on(hass, entity_id=None):
    """Turn all or specified switch on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data))


@bind_hass
def turn_off(hass, entity_id=None):
    """Turn all or specified switch off."""
    hass.add_job(async_turn_off, hass, entity_id)


@callback
@bind_hass
def async_turn_off(hass, entity_id=None):
    """Turn all or specified switch off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data))
