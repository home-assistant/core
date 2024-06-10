"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    ATTR_PARAMS,
    DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_START_PAUSE,
    SERVICE_STOP,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified vacuum on."""
    hass.add_job(async_turn_on, hass, entity_id)


async def async_turn_on(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified vacuum on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


@bind_hass
def turn_off(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified vacuum off."""
    hass.add_job(async_turn_off, hass, entity_id)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified vacuum off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


@bind_hass
def toggle(hass, entity_id=ENTITY_MATCH_ALL):
    """Toggle all or specified vacuum."""
    hass.add_job(async_toggle, hass, entity_id)


async def async_toggle(hass, entity_id=ENTITY_MATCH_ALL):
    """Toggle all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_TOGGLE, data, blocking=True)


@bind_hass
def locate(hass, entity_id=ENTITY_MATCH_ALL):
    """Locate all or specified vacuum."""
    hass.add_job(async_locate, hass, entity_id)


async def async_locate(hass, entity_id=ENTITY_MATCH_ALL):
    """Locate all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_LOCATE, data, blocking=True)


@bind_hass
def clean_spot(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or specified vacuum to perform a spot clean-up."""
    hass.add_job(async_clean_spot, hass, entity_id)


async def async_clean_spot(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or specified vacuum to perform a spot clean-up."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_CLEAN_SPOT, data, blocking=True)


@bind_hass
def return_to_base(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or specified vacuum to return to base."""
    hass.add_job(async_return_to_base, hass, entity_id)


async def async_return_to_base(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or specified vacuum to return to base."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_RETURN_TO_BASE, data, blocking=True)


@bind_hass
def start_pause(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or specified vacuum to start or pause the current task."""
    hass.add_job(async_start_pause, hass, entity_id)


async def async_start_pause(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or specified vacuum to start or pause the current task."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_START_PAUSE, data, blocking=True)


@bind_hass
def start(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or specified vacuum to start or resume the current task."""
    hass.add_job(async_start, hass, entity_id)


async def async_start(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or specified vacuum to start or resume the current task."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_START, data, blocking=True)


@bind_hass
def pause(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or the specified vacuum to pause the current task."""
    hass.add_job(async_pause, hass, entity_id)


async def async_pause(hass, entity_id=ENTITY_MATCH_ALL):
    """Tell all or the specified vacuum to pause the current task."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_PAUSE, data, blocking=True)


@bind_hass
def stop(hass, entity_id=ENTITY_MATCH_ALL):
    """Stop all or specified vacuum."""
    hass.add_job(async_stop, hass, entity_id)


async def async_stop(hass, entity_id=ENTITY_MATCH_ALL):
    """Stop all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    await hass.services.async_call(DOMAIN, SERVICE_STOP, data, blocking=True)


@bind_hass
def set_fan_speed(hass, fan_speed, entity_id=ENTITY_MATCH_ALL):
    """Set fan speed for all or specified vacuum."""
    hass.add_job(async_set_fan_speed, hass, fan_speed, entity_id)


async def async_set_fan_speed(hass, fan_speed, entity_id=ENTITY_MATCH_ALL):
    """Set fan speed for all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_FAN_SPEED] = fan_speed
    await hass.services.async_call(DOMAIN, SERVICE_SET_FAN_SPEED, data, blocking=True)


@bind_hass
def send_command(hass, command, params=None, entity_id=ENTITY_MATCH_ALL):
    """Send command to all or specified vacuum."""
    hass.add_job(async_send_command, hass, command, params, entity_id)


async def async_send_command(hass, command, params=None, entity_id=ENTITY_MATCH_ALL):
    """Send command to all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_COMMAND] = command
    if params is not None:
        data[ATTR_PARAMS] = params
    await hass.services.async_call(DOMAIN, SERVICE_SEND_COMMAND, data, blocking=True)
