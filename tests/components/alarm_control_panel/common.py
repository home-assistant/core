"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.alarm_control_panel import DOMAIN
from homeassistant.const import (
    ATTR_CODE, ATTR_ENTITY_ID, SERVICE_ALARM_TRIGGER,
    SERVICE_ALARM_DISARM, SERVICE_ALARM_ARM_HOME, SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_NIGHT, SERVICE_ALARM_ARM_CUSTOM_BYPASS)
from homeassistant.loader import bind_hass
from homeassistant.core import callback


@callback
@bind_hass
def async_alarm_disarm(hass, code=None, entity_id=None):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_ALARM_DISARM, data))


@bind_hass
def alarm_disarm(hass, code=None, entity_id=None):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_DISARM, data)


@callback
@bind_hass
def async_alarm_arm_home(hass, code=None, entity_id=None):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_HOME, data))


@bind_hass
def alarm_arm_home(hass, code=None, entity_id=None):
    """Send the alarm the command for arm home."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_ARM_HOME, data)


@callback
@bind_hass
def async_alarm_arm_away(hass, code=None, entity_id=None):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_AWAY, data))


@bind_hass
def alarm_arm_away(hass, code=None, entity_id=None):
    """Send the alarm the command for arm away."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_ARM_AWAY, data)


@callback
@bind_hass
def async_alarm_arm_night(hass, code=None, entity_id=None):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_NIGHT, data))


@bind_hass
def alarm_arm_night(hass, code=None, entity_id=None):
    """Send the alarm the command for arm night."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_ARM_NIGHT, data)


@callback
@bind_hass
def async_alarm_trigger(hass, code=None, entity_id=None):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_ALARM_TRIGGER, data))


@bind_hass
def alarm_trigger(hass, code=None, entity_id=None):
    """Send the alarm the command for trigger."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_TRIGGER, data)


@callback
@bind_hass
def async_alarm_arm_custom_bypass(hass, code=None, entity_id=None):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.async_create_task(
        hass.services.async_call(
            DOMAIN, SERVICE_ALARM_ARM_CUSTOM_BYPASS, data))


@bind_hass
def alarm_arm_custom_bypass(hass, code=None, entity_id=None):
    """Send the alarm the command for arm custom bypass."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_ALARM_ARM_CUSTOM_BYPASS, data)
