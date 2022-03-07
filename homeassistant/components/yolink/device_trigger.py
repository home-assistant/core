"""Provides device triggers for YoLink."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

# TODO specify your supported trigger types.
TRIGGER_TYPES = {
    "turned_on",
    "turned_off",
    "water_leak",
    "open",
    "closed",
    "motion_detected",
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for YoLink devices."""

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)
    _triggers: list[dict] = []
    if device.model in ["Siren"] or device.manufacturer != "YoLink":
        return _triggers

    trigger_basic = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device_id,
    }
    registry = await entity_registry.async_get_registry(hass)

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.platform != DOMAIN:
            continue
        if device.model in ["DoorSensor"]:
            if entry.device_class == "door":
                _triggers.append(
                    {
                        **trigger_basic,
                        CONF_TYPE: "open",
                        CONF_ENTITY_ID: entry.entity_id,
                    }
                )
                _triggers.append(
                    {
                        **trigger_basic,
                        CONF_TYPE: "closed",
                        CONF_ENTITY_ID: entry.entity_id,
                    }
                )
        elif device.model == "LeakSensor":
            if entry.device_class == "moisture":
                _triggers.append(
                    {
                        **trigger_basic,
                        CONF_TYPE: "water_leak",
                        CONF_ENTITY_ID: entry.entity_id,
                    }
                )
        elif device.model == "MotionSensor":
            if entry.device_class == "motion":
                _triggers.append(
                    {
                        **trigger_basic,
                        CONF_TYPE: "motion_detected",
                        CONF_ENTITY_ID: entry.entity_id,
                    }
                )
        elif device.model == "Outlet":
            _triggers.append(
                {
                    **trigger_basic,
                    CONF_TYPE: "turned_on",
                    CONF_ENTITY_ID: entry.entity_id,
                }
            )
            _triggers.append(
                {
                    **trigger_basic,
                    CONF_TYPE: "turned_off",
                    CONF_ENTITY_ID: entry.entity_id,
                }
            )
            break
    return _triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    # TODO Implement your own logic to attach triggers.
    # Use the existing state or event triggers from the automation integration.
    if config[CONF_TYPE] == "turned_on":
        to_state = STATE_ON
    elif config[CONF_TYPE] == "turned_off":
        to_state = STATE_OFF
    elif (
        config[CONF_TYPE] == "water_leak"
        or config[CONF_TYPE] == "motion_detected"
        or config[CONF_TYPE] == "open"
    ):
        to_state = STATE_ON
    elif config[CONF_TYPE] == "closed":
        to_state = STATE_OFF
    else:
        to_state = STATE_OFF

    state_config = {
        state.CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_TO: to_state,
    }
    state_config = state.TRIGGER_SCHEMA(state_config)
    return await state.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )
