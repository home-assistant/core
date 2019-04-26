"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.lock import DOMAIN
from homeassistant.const import (
    ATTR_CODE, ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK, SERVICE_OPEN)
from homeassistant.loader import bind_hass


@bind_hass
def lock(hass, entity_id=None, code=None):
    """Lock all or specified locks."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_LOCK, data)


async def async_lock(hass, entity_id=None, code=None):
    """Lock all or specified locks."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_LOCK, data, blocking=True)


@bind_hass
def unlock(hass, entity_id=None, code=None):
    """Unlock all or specified locks."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_UNLOCK, data)


async def async_unlock(hass, entity_id=None, code=None):
    """Lock all or specified locks."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_UNLOCK, data, blocking=True)


@bind_hass
def open_lock(hass, entity_id=None, code=None):
    """Open all or specified locks."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_OPEN, data)


async def async_open_lock(hass, entity_id=None, code=None):
    """Lock all or specified locks."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_OPEN, data, blocking=True)
