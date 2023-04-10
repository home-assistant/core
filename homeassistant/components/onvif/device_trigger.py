"""Provides device automations for ONVIF."""
from typing import List, Optional

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from ...helpers.trigger import TriggerInfo
from .const import CONF_SUBTYPE, CONF_UNIQUE_ID, DOMAIN
from .device import ONVIFDevice

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_UNIQUE_ID): str,
        vol.Required(CONF_TYPE): str,
        vol.Required(CONF_SUBTYPE): str,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> List[dict[str, str]]:
    """List device triggers for ONVIF devices."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device_conf = device_registry.async_get(device_id)

    triggers: list[dict[str, str]] = []
    for entry_id in device_conf.config_entries:
        config_entry: Optional[ConfigEntry] = hass.config_entries.async_get_entry(
            entry_id
        )
        assert config_entry is not None

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
                    CONF_SUBTYPE: event.event_id,
                }
            )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: "onvif_event",
        event_trigger.CONF_EVENT_DATA: {CONF_UNIQUE_ID: config[CONF_UNIQUE_ID]},
    }

    event_config = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
