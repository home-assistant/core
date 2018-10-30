"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.camera import (
    ATTR_FILENAME, DOMAIN, SERVICE_ENABLE_MOTION, SERVICE_SNAPSHOT)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, \
    SERVICE_TURN_ON
from homeassistant.core import callback
from homeassistant.loader import bind_hass


@bind_hass
async def async_turn_off(hass, entity_id=None):
    """Turn off camera."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
async def async_turn_on(hass, entity_id=None):
    """Turn on camera, and set operation mode."""
    data = {}
    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def enable_motion_detection(hass, entity_id=None):
    """Enable Motion Detection."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_ENABLE_MOTION, data))


@bind_hass
@callback
def async_snapshot(hass, filename, entity_id=None):
    """Make a snapshot from a camera."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_FILENAME] = filename

    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_SNAPSHOT, data))
