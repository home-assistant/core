# custom_components/rebooter_pro/device_trigger.py
from __future__ import annotations

import voluptuous as vol
from typing import Callable

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, CALLBACK_TYPE
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# Event name that __init__.py will fire
REBOOT_EVENT = f"{DOMAIN}_reboot_started"

# The three trigger "types" users can pick in the UI
TRIGGER_TYPES = {
    "reboot_started_any",
    "reboot_started_power_fail",
    "reboot_started_ping_fail",
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)

async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Return the list of triggers for this device."""
    base = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device_id,
    }
    return [{**base, CONF_TYPE: t} for t in TRIGGER_TYPES]

async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger by wrapping an 'event' trigger."""
    cfg = TRIGGER_SCHEMA(config)

    event_cfg = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: REBOOT_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                # match by device and type
                CONF_DEVICE_ID: cfg[CONF_DEVICE_ID],
                CONF_TYPE: cfg[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_cfg, action, trigger_info, platform_type="device"
    )
