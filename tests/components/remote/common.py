"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_ALTERNATIVE,
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DOMAIN,
    SERVICE_LEARN_COMMAND,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, activity=None, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified remote on."""
    data = {
        key: value
        for key, value in [(ATTR_ACTIVITY, activity), (ATTR_ENTITY_ID, entity_id)]
        if value is not None
    }
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def turn_off(hass, activity=None, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified remote off."""
    data = {}
    if activity:
        data[ATTR_ACTIVITY] = activity

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def send_command(
    hass,
    command,
    entity_id=ENTITY_MATCH_ALL,
    device=None,
    num_repeats=None,
    delay_secs=None,
):
    """Send a command to a device."""
    data = {ATTR_COMMAND: command}
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if device:
        data[ATTR_DEVICE] = device

    if num_repeats:
        data[ATTR_NUM_REPEATS] = num_repeats

    if delay_secs:
        data[ATTR_DELAY_SECS] = delay_secs

    hass.services.call(DOMAIN, SERVICE_SEND_COMMAND, data)


@bind_hass
def learn_command(
    hass,
    entity_id=ENTITY_MATCH_ALL,
    device=None,
    command=None,
    alternative=None,
    timeout=None,
):
    """Learn a command from a device."""
    data = {}
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if device:
        data[ATTR_DEVICE] = device

    if command:
        data[ATTR_COMMAND] = command

    if alternative:
        data[ATTR_ALTERNATIVE] = alternative

    if timeout:
        data[ATTR_TIMEOUT] = timeout

    hass.services.call(DOMAIN, SERVICE_LEARN_COMMAND, data)
