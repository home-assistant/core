"""Provides device triggers for Xiaomi BLE."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_MAC,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_PROPERTIES, EVENT_TYPE, XIAOMI_BLE_EVENT

MOTION_TRIGGER_TYPES = {"motion_detected", "motion_clear"}

MUE4094RT_MOTION_TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(MOTION_TRIGGER_TYPES),
    }
)

TRIGGER_SCHEMA = vol.Any(
    MUE4094RT_MOTION_TRIGGER_SCHEMA,
)

TRIGGERS_BY_MODEL = {"MUE4094RT": MOTION_TRIGGER_TYPES}


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List a list of triggers for Xiaomi BLE devices."""

    # Check if device is a MUE4094RT motion sensor device.  Return empty if not.
    if not (triggers := _async_get_triggers_by_model(hass, device_id)):
        return []

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger,
        }
        for trigger in triggers
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    return await event_trigger.async_attach_trigger(
        hass,
        event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: CONF_EVENT,
                event_trigger.CONF_EVENT_TYPE: XIAOMI_BLE_EVENT,
                event_trigger.CONF_EVENT_DATA: {
                    CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                    CONF_ADDRESS: config[CONF_MAC],
                    EVENT_TYPE: config[EVENT_TYPE],
                    EVENT_PROPERTIES: config[EVENT_PROPERTIES],
                },
            }
        ),
        action,
        trigger_info,
        platform_type="device",
    )


def _async_get_triggers_by_model(
    hass: HomeAssistant, device_id: str
) -> set[str] | None:
    """Get a Xiaomi BLE motion device for the given device registry device id."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device and device.model and (triggers := TRIGGERS_BY_MODEL.get(device.model)):
        return triggers
    return None
