"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED, ATTR_PARAMS, DOMAIN, SERVICE_CLEAN_SPOT, SERVICE_LOCATE,
    SERVICE_PAUSE, SERVICE_SEND_COMMAND, SERVICE_SET_FAN_SPEED, SERVICE_START,
    SERVICE_START_PAUSE, SERVICE_STOP, SERVICE_RETURN_TO_BASE)
from homeassistant.const import (
    ATTR_COMMAND, ATTR_ENTITY_ID, SERVICE_TOGGLE,
    SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id=None):
    """Turn all or specified vacuum on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def turn_off(hass, entity_id=None):
    """Turn all or specified vacuum off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def toggle(hass, entity_id=None):
    """Toggle all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


@bind_hass
def locate(hass, entity_id=None):
    """Locate all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_LOCATE, data)


@bind_hass
def clean_spot(hass, entity_id=None):
    """Tell all or specified vacuum to perform a spot clean-up."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_CLEAN_SPOT, data)


@bind_hass
def return_to_base(hass, entity_id=None):
    """Tell all or specified vacuum to return to base."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_RETURN_TO_BASE, data)


@bind_hass
def start_pause(hass, entity_id=None):
    """Tell all or specified vacuum to start or pause the current task."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_START_PAUSE, data)


@bind_hass
def start(hass, entity_id=None):
    """Tell all or specified vacuum to start or resume the current task."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_START, data)


@bind_hass
def pause(hass, entity_id=None):
    """Tell all or the specified vacuum to pause the current task."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_PAUSE, data)


@bind_hass
def stop(hass, entity_id=None):
    """Stop all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_STOP, data)


@bind_hass
def set_fan_speed(hass, fan_speed, entity_id=None):
    """Set fan speed for all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_FAN_SPEED] = fan_speed
    hass.services.call(DOMAIN, SERVICE_SET_FAN_SPEED, data)


@bind_hass
def send_command(hass, command, params=None, entity_id=None):
    """Send command to all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_COMMAND] = command
    if params is not None:
        data[ATTR_PARAMS] = params
    hass.services.call(DOMAIN, SERVICE_SEND_COMMAND, data)
