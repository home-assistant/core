"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.alarm_control_panel import DOMAIN
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)


async def async_alarm_disarm(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_DISARM, data, blocking=True)


async def async_alarm_arm_home(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_HOME, data, blocking=True)


async def async_alarm_arm_away(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_AWAY, data, blocking=True)


async def async_alarm_arm_night(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_ARM_NIGHT, data, blocking=True)


async def async_alarm_arm_vacation(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for vacation mode."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, SERVICE_ALARM_ARM_VACATION, data, blocking=True
    )


async def async_alarm_trigger(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_ALARM_TRIGGER, data, blocking=True)


async def async_alarm_arm_custom_bypass(hass, code=None, entity_id=ENTITY_MATCH_ALL):
    """Send the alarm the command for disarm."""
    data = {}
    if code:
        data[ATTR_CODE] = code
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, SERVICE_ALARM_ARM_CUSTOM_BYPASS, data, blocking=True
    )
