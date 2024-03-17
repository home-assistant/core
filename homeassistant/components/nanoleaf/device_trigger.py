"""Provides device triggers for Nanoleaf."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import DeviceNotFound
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, NANOLEAF_EVENT, TOUCH_GESTURE_TRIGGER_MAP, TOUCH_MODELS

TRIGGER_TYPES = TOUCH_GESTURE_TRIGGER_MAP.values()

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Nanoleaf devices."""
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise DeviceNotFound(f"Device ID {device_id} is not valid")
    if device_entry.model not in TOUCH_MODELS:
        return []
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in TRIGGER_TYPES
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: NANOLEAF_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_TYPE: config[CONF_TYPE],
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
