"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.automation import (
    CONF_SKIP_CONDITION,
    DOMAIN,
    SERVICE_TRIGGER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_RELOAD,
    SERVICE_TOGGLE,
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


@bind_hass
async def async_toggle(hass, entity_id=ENTITY_MATCH_ALL):
    """Toggle specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TOGGLE, data)


@bind_hass
async def async_trigger(hass, entity_id=ENTITY_MATCH_ALL, skip_condition=True):
    """Trigger specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[CONF_SKIP_CONDITION] = skip_condition
    await hass.services.async_call(DOMAIN, SERVICE_TRIGGER, data)


@bind_hass
async def async_reload(hass, context=None):
    """Reload the automation from config."""
    await hass.services.async_call(
        DOMAIN, SERVICE_RELOAD, blocking=True, context=context
    )
