"""Provides device automations for RFXCOM RFXtrx."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.components.rfxtrx.const import EVENT_RFXTRX_EVENT
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN
from .helpers import async_get_device_object

CONF_SUBTYPE = "subtype"

TRIGGER_TYPES = {"command", "status"}
TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_SUBTYPE): str,
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for RFXCOM RFXtrx devices."""
    triggers = []

    device = async_get_device_object(hass, device_id)
    if device:
        if hasattr(device, "COMMANDS"):
            for command in device.COMMANDS.values():
                triggers.append(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_TYPE: "command",
                        CONF_SUBTYPE: command,
                    }
                )
        if hasattr(device, "STATUS"):
            for status in device.STATUS.values():
                triggers.append(
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_TYPE: "status",
                        CONF_SUBTYPE: status,
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

    event_data = {ATTR_DEVICE_ID: config[CONF_DEVICE_ID]}

    if config[CONF_TYPE] == "command":
        event_data["values"] = {"Command": config[CONF_SUBTYPE]}
    elif config[CONF_TYPE] == "status":
        event_data["values"] = {"Status": config[CONF_SUBTYPE]}
    else:
        return None

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_RFXTRX_EVENT,
            event_trigger.CONF_EVENT_DATA: event_data,
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, automation_info, platform_type="device"
    )
