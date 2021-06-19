"""Provides device triggers for Z-Wave JS."""
from __future__ import annotations

import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import NodeStatus

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event, state
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry,
    entity_registry,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_DATA_TYPE,
    ATTR_EVENT,
    ATTR_EVENT_LABEL,
    ATTR_EVENT_TYPE,
    ATTR_LABEL,
    ATTR_TYPE,
    DOMAIN,
    ZWAVE_JS_NOTIFICATION_EVENT,
)
from .helpers import (
    async_get_node_from_device_id,
    async_get_node_status_sensor_entity_id,
)

# Trigger types
ENTRY_CONTROL_NOTIFICATION = "event.entry_control_notification"
NOTIFICATION_NOTIFICATION = "event.notification_notification"
NODE_STATUS = "state.node_status"

NOTIFICATION_EVENT_CC_MAPPINGS = (
    (ENTRY_CONTROL_NOTIFICATION, CommandClass.ENTRY_CONTROL),
    (NOTIFICATION_NOTIFICATION, CommandClass.NOTIFICATION),
)

BASE_EVENT_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Optional(ATTR_COMMAND_CLASS): vol.In([cc.value for cc in CommandClass]),
    }
)

BASE_STATE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
    }
)

NOTIFICATION_NOTIFICATION_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): NOTIFICATION_NOTIFICATION,
        vol.Optional(f"{ATTR_TYPE}."): vol.Coerce(int),
        vol.Optional(ATTR_LABEL): cv.string,
        vol.Optional(ATTR_EVENT): vol.Coerce(int),
        vol.Optional(ATTR_EVENT_LABEL): cv.string,
    }
)

ENTRY_CONTROL_NOTIFICATION_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): ENTRY_CONTROL_NOTIFICATION,
        vol.Optional(ATTR_EVENT_TYPE): vol.Coerce(int),
        vol.Optional(ATTR_DATA_TYPE): vol.Coerce(int),
    }
)

NODE_STATUSES = [node_status.name.lower() for node_status in NodeStatus]

NODE_STATUS_SCHEMA = BASE_STATE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): NODE_STATUS,
        vol.Optional(state.CONF_FROM): vol.In(NODE_STATUSES),
        vol.Optional(state.CONF_TO): vol.In(NODE_STATUSES),
        vol.Optional(state.CONF_FOR): cv.positive_time_period_dict,
    }
)

TRIGGER_SCHEMA = vol.Any(
    ENTRY_CONTROL_NOTIFICATION_SCHEMA,
    NOTIFICATION_NOTIFICATION_SCHEMA,
    NODE_STATUS_SCHEMA,
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device triggers for Z-Wave JS devices."""
    dev_reg = device_registry.async_get(hass)
    node = async_get_node_from_device_id(hass, device_id, dev_reg)

    triggers = []
    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    # We can add a node status trigger if the node status sensor is enabled
    ent_reg = entity_registry.async_get(hass)
    entity_id = async_get_node_status_sensor_entity_id(
        hass, device_id, ent_reg, dev_reg
    )
    if (entity := ent_reg.async_get(entity_id)) is not None and not entity.disabled:
        triggers = [{**base_trigger, CONF_TYPE: NODE_STATUS, CONF_ENTITY_ID: entity_id}]

    # Handle notification event triggers
    triggers.extend(
        [
            {**base_trigger, CONF_TYPE: event_type, ATTR_COMMAND_CLASS: command_class}
            for event_type, command_class in NOTIFICATION_EVENT_CC_MAPPINGS
            if any(cc.id == command_class for cc in node.command_classes)
        ]
    )

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
    state_config = {state.CONF_PLATFORM: "state"}

    trigger_type = config[CONF_TYPE].split(".")[0]

    if ATTR_COMMAND_CLASS in config:
        event_data[ATTR_COMMAND_CLASS] = config[ATTR_COMMAND_CLASS]

    # Take input data from automation trigger UI and add it to the trigger we are
    # attaching to
    if trigger_type == "event":
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

    if trigger_type == "state" and config[CONF_TYPE] == NODE_STATUS:
        state_config[state.CONF_ENTITY_ID] = config[CONF_ENTITY_ID]
        for param in (state.CONF_FOR, state.CONF_FROM, state.CONF_TO):
            if val := config.get(param):
                state_config[param] = val

        return await state.async_attach_trigger(
            hass, state_config, action, automation_info, platform_type="device"
        )

    raise HomeAssistantError("Trigger type not recognized")


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    # Add additional fields to the automation trigger UI
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

    if config[CONF_TYPE] == NODE_STATUS:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(state.CONF_FROM): vol.In(NODE_STATUSES),
                    vol.Optional(state.CONF_TO): vol.In(NODE_STATUSES),
                    vol.Optional(state.CONF_FOR): cv.positive_time_period_dict,
                }
            )
        }

    return {}
