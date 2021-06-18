"""Provides device triggers for Z-Wave JS."""
from __future__ import annotations

import voluptuous as vol
from zwave_js_server.const import CommandClass

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_DATA_TYPE,
    ATTR_EVENT,
    ATTR_EVENT_LABEL,
    ATTR_EVENT_TYPE,
    ATTR_LABEL,
    ATTR_NODE_ID,
    ATTR_TYPE,
    DOMAIN,
    ZWAVE_JS_NOTIFICATION_EVENT,
)
from .helpers import async_get_node_from_device_id

ENTRY_CONTROL_NOTIFICATION = "entry_control_notification"
NOTIFICATION_NOTIFICATION = "notification_notification"

NOTIFICATION_EVENT_CC_MAPPINGS = (
    (ENTRY_CONTROL_NOTIFICATION, CommandClass.ENTRY_CONTROL),
    (NOTIFICATION_NOTIFICATION, CommandClass.NOTIFICATION),
)

BASE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_NODE_ID): int,
        vol.Optional(ATTR_COMMAND_CLASS): vol.In([cc.value for cc in CommandClass]),
    }
)

NOTIFICATION_NOTIFICATION_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): NOTIFICATION_NOTIFICATION,
        vol.Optional(f"{ATTR_TYPE}."): vol.Coerce(int),
        vol.Optional(ATTR_LABEL): cv.string,
        vol.Optional(ATTR_EVENT): vol.Coerce(int),
        vol.Optional(ATTR_EVENT_LABEL): cv.string,
    }
)

ENTRY_CONTROL_NOTIFICATION_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): ENTRY_CONTROL_NOTIFICATION,
        vol.Optional(ATTR_EVENT_TYPE): vol.Coerce(int),
        vol.Optional(ATTR_DATA_TYPE): vol.Coerce(int),
    }
)

TRIGGER_SCHEMA = vol.Any(
    ENTRY_CONTROL_NOTIFICATION_SCHEMA,
    NOTIFICATION_NOTIFICATION_SCHEMA,
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for Z-Wave JS devices."""
    registry = device_registry.async_get(hass)
    node = async_get_node_from_device_id(hass, device_id, registry)
    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        ATTR_NODE_ID: node.node_id,
        CONF_DOMAIN: DOMAIN,
    }

    # Handle notification event triggers
    triggers = [
        {**base_trigger, CONF_TYPE: event_type, ATTR_COMMAND_CLASS: command_class}
        for event_type, command_class in NOTIFICATION_EVENT_CC_MAPPINGS
        if any(cc.id == command_class for cc in node.command_classes)
    ]

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    event_data = {CONF_DEVICE_ID: config[CONF_DEVICE_ID]}
    event_config = {
        event.CONF_PLATFORM: "event",
        event.CONF_EVENT_DATA: event_data,
    }

    if ATTR_COMMAND_CLASS in config:
        event_data[ATTR_COMMAND_CLASS] = config[ATTR_COMMAND_CLASS]

    if config[CONF_TYPE] == ENTRY_CONTROL_NOTIFICATION:
        event_config[event.CONF_EVENT_TYPE] = ZWAVE_JS_NOTIFICATION_EVENT
        for param in (ATTR_EVENT_TYPE, ATTR_DATA_TYPE):
            if (val := config.get(param)) is not None:
                event_data[param] = val
    elif config[CONF_TYPE] == NOTIFICATION_NOTIFICATION:
        event_config[event.CONF_EVENT_TYPE] = ZWAVE_JS_NOTIFICATION_EVENT
        for param in (ATTR_LABEL, ATTR_EVENT_LABEL):
            if val := config.get(param):
                event_data[param] = val
        if (val := config.get(ATTR_EVENT)) is not None:
            event_data[ATTR_EVENT] = val
        if (val := config.get(f"{ATTR_TYPE}.")) is not None:
            event_data[ATTR_TYPE] = val

    event_config = event.TRIGGER_SCHEMA(event_config)
    return await event.async_attach_trigger(  # type: ignore
        hass, event_config, action, automation_info, platform_type="device"
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    if config[CONF_TYPE] == NOTIFICATION_NOTIFICATION:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(f"{ATTR_TYPE}."): cv.string,
                    vol.Optional(ATTR_LABEL): cv.string,
                    vol.Optional(ATTR_EVENT): cv.string,
                    vol.Optional(ATTR_EVENT_LABEL): cv.string,
                }
            )
        }

    if config[CONF_TYPE] == ENTRY_CONTROL_NOTIFICATION:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(ATTR_EVENT_TYPE): cv.string,
                    vol.Optional(ATTR_DATA_TYPE): cv.string,
                }
            )
        }

    return {}
