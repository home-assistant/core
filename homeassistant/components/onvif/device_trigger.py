"""Provides device automations for ONVIF."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    event as automation_event,
)
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SUBTYPE, CONF_UNIQUE_ID, DOMAIN
from .device import ONVIFDevice

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_UNIQUE_ID): str,
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_SUBTYPE): str,
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for ONVIF devices."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_conf = device_registry.async_get(device_id)

    triggers = []
    for entry_id in device_conf.config_entries:
        config_entry: ConfigEntry = hass.config_entries.async_get_entry(entry_id)

        if config_entry.domain != DOMAIN:
            continue

        device: ONVIFDevice = hass.data[DOMAIN][config_entry.unique_id]
        for event in device.events.get_platform("event"):
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_UNIQUE_ID: event.uid,
                    CONF_TYPE: "event",
                    CONF_SUBTYPE: event.name,
                }
            )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)

    event_config = {
        automation_event.CONF_PLATFORM: "event",
        automation_event.CONF_EVENT_TYPE: "onvif_event",
        automation_event.CONF_EVENT_DATA: {CONF_UNIQUE_ID: config[CONF_UNIQUE_ID]},
    }

    event_config = automation_event.TRIGGER_SCHEMA(event_config)
    return await automation_event.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
