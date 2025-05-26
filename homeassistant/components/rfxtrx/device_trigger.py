"""Provides device automations for RFXCOM RFXtrx."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN
from .const import EVENT_RFXTRX_EVENT
from .helpers import async_get_device_object

CONF_SUBTYPE = "subtype"

CONF_TYPE_COMMAND = "command"
CONF_TYPE_STATUS = "status"

TRIGGER_SELECTION = {
    CONF_TYPE_COMMAND: "COMMANDS",
    CONF_TYPE_STATUS: "STATUS",
}
TRIGGER_TYPES = [
    CONF_TYPE_COMMAND,
    CONF_TYPE_STATUS,
]
TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_SUBTYPE): str,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for RFXCOM RFXtrx devices."""
    device = async_get_device_object(hass, device_id)

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: conf_type,
            CONF_SUBTYPE: command,
        }
        for conf_type in TRIGGER_TYPES
        for command in getattr(device, TRIGGER_SELECTION[conf_type], {}).values()
    ]


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    device = async_get_device_object(hass, config[CONF_DEVICE_ID])

    action_type = config[CONF_TYPE]
    sub_type = config[CONF_SUBTYPE]
    commands = getattr(device, TRIGGER_SELECTION[action_type], {})
    if config[CONF_SUBTYPE] not in commands.values():
        raise InvalidDeviceAutomationConfig(
            f"Subtype {sub_type} not found in device triggers {commands}"
        )

    return config


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)

    event_data = {ATTR_DEVICE_ID: config[CONF_DEVICE_ID]}

    if config[CONF_TYPE] == CONF_TYPE_COMMAND:
        event_data["values"] = {"Command": config[CONF_SUBTYPE]}
    elif config[CONF_TYPE] == CONF_TYPE_STATUS:
        event_data["values"] = {"Sensor Status": config[CONF_SUBTYPE]}

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_RFXTRX_EVENT,
            event_trigger.CONF_EVENT_DATA: event_data,
        }
    )

    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
