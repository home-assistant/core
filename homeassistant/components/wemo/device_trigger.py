"""Triggers for WeMo devices."""
from __future__ import annotations

from pywemo.subscribe import EVENT_TYPE_LONG_PRESS
import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN as WEMO_DOMAIN, WEMO_SUBSCRIPTION_EVENT
from .wemo_device import async_get_coordinator

TRIGGER_TYPES = {EVENT_TYPE_LONG_PRESS}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Return a list of triggers."""

    wemo_trigger = {
        # Required fields of TRIGGER_BASE_SCHEMA
        CONF_PLATFORM: "device",
        CONF_DOMAIN: WEMO_DOMAIN,
        CONF_DEVICE_ID: device_id,
    }

    coordinator = async_get_coordinator(hass, device_id)
    triggers = []

    # Check for long press support.
    if coordinator.supports_long_press:
        triggers.append(
            {
                # Required fields of TRIGGER_SCHEMA
                CONF_TYPE: EVENT_TYPE_LONG_PRESS,
                **wemo_trigger,
            }
        )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: WEMO_SUBSCRIPTION_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
                CONF_TYPE: config[CONF_TYPE],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
