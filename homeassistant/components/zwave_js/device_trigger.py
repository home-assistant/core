"""Provides device triggers for Z-Wave JS."""
from __future__ import annotations

from dataclasses import dataclass, field
import functools
from typing import Any, Callable

import voluptuous as vol
from zwave_js_server.const import CommandClass, ConfigurationValueType
from zwave_js_server.model.node import Node
from zwave_js_server.model.value import Value

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event, state
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
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
    ATTR_ENDPOINT,
    ATTR_EVENT,
    ATTR_EVENT_LABEL,
    ATTR_EVENT_TYPE,
    ATTR_LABEL,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_TYPE,
    ATTR_VALUE,
    ATTR_VALUE_RAW,
    DATA_DEVICE_TRIGGER_TRACKERS,
    DOMAIN,
    LOGGER,
    ZWAVE_JS_DEVICE_TRIGGER_VALUE_UPDATED_EVENT,
    ZWAVE_JS_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
)
from .entity import EVENT_VALUE_UPDATED
from .helpers import (
    async_get_node_from_device_id,
    async_get_node_status_sensor_entity_id,
    get_zwave_value_from_config,
)

CONF_SUBTYPE = "subtype"
CONF_VALUE_ID = "value_id"

# Trigger types
ENTRY_CONTROL_NOTIFICATION = "event.notification.entry_control"
NOTIFICATION_NOTIFICATION = "event.notification.notification"
BASIC_VALUE_NOTIFICATION = "event.value_notification.basic"
CENTRAL_SCENE_VALUE_NOTIFICATION = "event.value_notification.central_scene"
SCENE_ACTIVATION_VALUE_NOTIFICATION = "event.value_notification.scene_activation"
CONFIG_PARAMETER_VALUE_UPDATE = "event.value_update.config_parameter"
VALUE_VALUE_UPDATE = "event.value_update.value"
NODE_STATUS = "state.node_status"

VALUE_SCHEMA = vol.Any(
    bool,
    vol.Coerce(int),
    vol.Coerce(float),
    cv.boolean,
    cv.string,
)

NOTIFICATION_EVENT_CC_MAPPINGS = (
    (ENTRY_CONTROL_NOTIFICATION, CommandClass.ENTRY_CONTROL),
    (NOTIFICATION_NOTIFICATION, CommandClass.NOTIFICATION),
)

# Event based trigger schemas
BASE_EVENT_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_COMMAND_CLASS): vol.In([cc.value for cc in CommandClass]),
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

BASE_VALUE_NOTIFICATION_EVENT_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        vol.Required(ATTR_PROPERTY): vol.Any(int, str),
        vol.Required(ATTR_PROPERTY_KEY): vol.Any(None, int, str),
        vol.Required(ATTR_ENDPOINT): vol.Coerce(int),
        vol.Optional(ATTR_VALUE): vol.Coerce(int),
        vol.Required(CONF_SUBTYPE): cv.string,
    }
)

BASIC_VALUE_NOTIFICATION_SCHEMA = BASE_VALUE_NOTIFICATION_EVENT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): BASIC_VALUE_NOTIFICATION,
    }
)

CENTRAL_SCENE_VALUE_NOTIFICATION_SCHEMA = BASE_VALUE_NOTIFICATION_EVENT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): CENTRAL_SCENE_VALUE_NOTIFICATION,
    }
)

SCENE_ACTIVATION_VALUE_NOTIFICATION_SCHEMA = (
    BASE_VALUE_NOTIFICATION_EVENT_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): SCENE_ACTIVATION_VALUE_NOTIFICATION,
        }
    )
)

BASE_VALUE_UPDATE_EVENT_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        vol.Required(ATTR_PROPERTY): vol.Any(int, str),
        vol.Optional(ATTR_PROPERTY_KEY): vol.Any(None, vol.Coerce(int), str),
        vol.Optional(ATTR_ENDPOINT): vol.Any(None, vol.Coerce(int)),
        vol.Optional(state.CONF_FROM): VALUE_SCHEMA,
        vol.Optional(state.CONF_TO): VALUE_SCHEMA,
    }
)

CONFIG_PARAMETER_VALUE_UPDATE_SCHEMA = BASE_VALUE_UPDATE_EVENT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): CONFIG_PARAMETER_VALUE_UPDATE,
        vol.Required(CONF_SUBTYPE): cv.string,
    }
)

VALUE_VALUE_UPDATE_SCHEMA = BASE_VALUE_UPDATE_EVENT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): VALUE_VALUE_UPDATE,
    }
)

# State based trigger schemas
BASE_STATE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
    }
)

NODE_STATUSES = ["asleep", "awake", "dead", "alive"]

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
    BASIC_VALUE_NOTIFICATION_SCHEMA,
    CENTRAL_SCENE_VALUE_NOTIFICATION_SCHEMA,
    SCENE_ACTIVATION_VALUE_NOTIFICATION_SCHEMA,
    CONFIG_PARAMETER_VALUE_UPDATE_SCHEMA,
    VALUE_VALUE_UPDATE_SCHEMA,
    NODE_STATUS_SCHEMA,
)


@dataclass
class AutomationTracker:
    """Class to store an unsubscription callback for a given automation."""

    value_tracker: ValueTracker
    id: str
    unsub: Callable


@dataclass
class ValueTracker:
    """Class to store tracked automations for a given value."""

    device_tracker: DeviceTracker
    zwave_value: Value
    prev_value: Any
    automations: dict[str, AutomationTracker] = field(default_factory=dict, init=False)


@dataclass
class DeviceTracker:
    """Class to store tracked values for a given device/node."""

    hass: HomeAssistant
    config_entry_id: str
    device_id: str
    node: Node
    value_update_unsub: Callable | None = field(default=None, init=False)
    values: dict[str, ValueTracker] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Handle post initialization."""
        self.value_update_unsub = self.node.on(
            EVENT_VALUE_UPDATED,
            lambda event: self.fire_value_updated_event(event["value"]),
        )

    @callback
    def fire_value_updated_event(self, value: Value) -> None:
        """Fire a value updated event if needed."""
        if (value_tracker := self.values.get(value.value_id)) is None:
            return

        from_value = value_tracker.prev_value
        to_value = value_tracker.prev_value = value.value
        event_data = {
            ATTR_DEVICE_ID: self.device_id,
            ATTR_COMMAND_CLASS: value.command_class,
            ATTR_PROPERTY: value.property_,
            ATTR_PROPERTY_KEY: value.property_key,
            ATTR_ENDPOINT: value.endpoint,
            state.CONF_FROM: from_value,
            state.CONF_TO: to_value,
        }
        LOGGER.debug(
            "Firing device trigger event: %s",
            {k: v for k, v in event_data.items() if v is not None},
        )
        self.hass.bus.async_fire(
            ZWAVE_JS_DEVICE_TRIGGER_VALUE_UPDATED_EVENT,
            {k: v for k, v in event_data.items() if v is not None},
        )


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)
    if config[CONF_TYPE] == VALUE_VALUE_UPDATE:
        node = async_get_node_from_device_id(hass, config[CONF_DEVICE_ID])
        get_zwave_value_from_config(node, config)

    return config


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
        triggers.append(
            {**base_trigger, CONF_TYPE: NODE_STATUS, CONF_ENTITY_ID: entity_id}
        )

    # Handle notification event triggers
    triggers.extend(
        [
            {**base_trigger, CONF_TYPE: event_type, ATTR_COMMAND_CLASS: command_class}
            for event_type, command_class in NOTIFICATION_EVENT_CC_MAPPINGS
            if any(cc.id == command_class for cc in node.command_classes)
        ]
    )

    # Handle central scene value notification event triggers
    triggers.extend(
        [
            {
                **base_trigger,
                CONF_TYPE: CENTRAL_SCENE_VALUE_NOTIFICATION,
                ATTR_PROPERTY: value.property_,
                ATTR_PROPERTY_KEY: value.property_key,
                ATTR_ENDPOINT: value.endpoint,
                ATTR_COMMAND_CLASS: CommandClass.CENTRAL_SCENE,
                CONF_SUBTYPE: f"Endpoint {value.endpoint} Scene {value.property_key}",
            }
            for value in node.get_command_class_values(
                CommandClass.CENTRAL_SCENE
            ).values()
            if value.property_ == "scene"
        ]
    )

    # Handle scene activation value notification event triggers
    triggers.extend(
        [
            {
                **base_trigger,
                CONF_TYPE: SCENE_ACTIVATION_VALUE_NOTIFICATION,
                ATTR_PROPERTY: value.property_,
                ATTR_PROPERTY_KEY: value.property_key,
                ATTR_ENDPOINT: value.endpoint,
                ATTR_COMMAND_CLASS: CommandClass.SCENE_ACTIVATION,
                CONF_SUBTYPE: f"Endpoint {value.endpoint}",
            }
            for value in node.get_command_class_values(
                CommandClass.SCENE_ACTIVATION
            ).values()
            if value.property_ == "sceneId"
        ]
    )

    # Handle basic value notification event triggers
    # Nodes will only send Basic CC value notifications if a compatibility flag is set
    if node.device_config.compat.get("treatBasicSetAsEvent", False):
        triggers.extend(
            [
                {
                    **base_trigger,
                    CONF_TYPE: BASIC_VALUE_NOTIFICATION,
                    ATTR_PROPERTY: value.property_,
                    ATTR_PROPERTY_KEY: value.property_key,
                    ATTR_ENDPOINT: value.endpoint,
                    ATTR_COMMAND_CLASS: CommandClass.BASIC,
                    CONF_SUBTYPE: f"Endpoint {value.endpoint}",
                }
                for value in node.get_command_class_values(CommandClass.BASIC).values()
                if value.property_ == "event"
            ]
        )

    # Generic value update event trigger
    triggers.append({**base_trigger, CONF_TYPE: VALUE_VALUE_UPDATE})

    # Config parameter value update event triggers
    triggers.extend(
        [
            {
                **base_trigger,
                CONF_TYPE: CONFIG_PARAMETER_VALUE_UPDATE,
                ATTR_PROPERTY: config_value.property_,
                ATTR_PROPERTY_KEY: config_value.property_key,
                ATTR_ENDPOINT: config_value.endpoint,
                ATTR_COMMAND_CLASS: config_value.command_class,
                CONF_SUBTYPE: f"{config_value.value_id} ({config_value.property_name})",
            }
            for config_value in node.get_configuration_values().values()
        ]
    )

    return triggers


def copy_available_params(
    input_dict: dict, output_dict: dict, params: list[str]
) -> None:
    """Copy available params from input into output."""
    for param in params:
        if (val := input_dict.get(param)) not in ("", None):
            output_dict[param] = val


@callback
def _detach_trigger(hass: HomeAssistant, automation_tracker: AutomationTracker) -> None:
    """Detach trigger and clean tracker up."""
    value_tracker = automation_tracker.value_tracker
    device_tracker = value_tracker.device_tracker
    device_id = device_tracker.device_id
    entry_id = device_tracker.config_entry_id

    # Detach the trigger
    automation_tracker.unsub()

    # If after unsubscribing for this automation, the value tracker has no automations
    # left that are still subscribed, we can pop the value from the device tracker
    value_tracker.automations.pop(automation_tracker.id)
    if not value_tracker.automations:
        device_tracker.values.pop(value_tracker.zwave_value.value_id)

    # If we have no values left to track for this device, we can unsub from value
    # updates for this device and pop the device tracker
    if not device_tracker.values:
        if device_tracker.value_update_unsub is not None:
            device_tracker.value_update_unsub()
        hass.data[DOMAIN][entry_id][DATA_DEVICE_TRIGGER_TRACKERS].pop(device_id)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trigger_type = config[CONF_TYPE]
    # Our convention for trigger types is to have the trigger type at the beginning
    # delimited by a `.`
    trigger_platform = trigger_type.split(".")[0]

    dev_reg = device_registry.async_get(hass)
    device_id = config[CONF_DEVICE_ID]
    device = dev_reg.async_get(device_id)
    if not device:
        raise HomeAssistantError(
            f"Device ID {device_id} is not a valid zwave_js device"
        )
    config_entry_id = next(entry for entry in device.config_entries)
    trigger_data = automation_info["trigger_data"]
    automation_id = (
        f"{automation_info['name']}.{trigger_data['id']}.{trigger_data['idx']}"
    )

    node = async_get_node_from_device_id(hass, device_id, dev_reg=dev_reg)
    value = (
        get_zwave_value_from_config(node, config) if ATTR_PROPERTY in config else None
    )

    # event triggers
    if trigger_platform == "event":
        event_data = {CONF_DEVICE_ID: device_id}
        event_config = {
            event.CONF_PLATFORM: "event",
            event.CONF_EVENT_DATA: event_data,
        }

        if ATTR_COMMAND_CLASS in config:
            event_data[ATTR_COMMAND_CLASS] = config[ATTR_COMMAND_CLASS]

        if trigger_type == ENTRY_CONTROL_NOTIFICATION:
            event_config[event.CONF_EVENT_TYPE] = ZWAVE_JS_NOTIFICATION_EVENT
            copy_available_params(config, event_data, [ATTR_EVENT_TYPE, ATTR_DATA_TYPE])
        elif trigger_type == NOTIFICATION_NOTIFICATION:
            event_config[event.CONF_EVENT_TYPE] = ZWAVE_JS_NOTIFICATION_EVENT
            copy_available_params(
                config, event_data, [ATTR_LABEL, ATTR_EVENT_LABEL, ATTR_EVENT]
            )
            if (val := config.get(f"{ATTR_TYPE}.")) not in ("", None):
                event_data[ATTR_TYPE] = val
        elif trigger_type in (
            BASIC_VALUE_NOTIFICATION,
            CENTRAL_SCENE_VALUE_NOTIFICATION,
            SCENE_ACTIVATION_VALUE_NOTIFICATION,
        ):
            event_config[event.CONF_EVENT_TYPE] = ZWAVE_JS_VALUE_NOTIFICATION_EVENT
            copy_available_params(
                config, event_data, [ATTR_PROPERTY, ATTR_PROPERTY_KEY, ATTR_ENDPOINT]
            )
            if ATTR_VALUE in config:
                event_data[ATTR_VALUE_RAW] = config[ATTR_VALUE]
        elif trigger_type in (CONFIG_PARAMETER_VALUE_UPDATE, VALUE_VALUE_UPDATE):
            event_config[
                event.CONF_EVENT_TYPE
            ] = ZWAVE_JS_DEVICE_TRIGGER_VALUE_UPDATED_EVENT
            copy_available_params(
                config,
                event_data,
                [
                    ATTR_PROPERTY,
                    ATTR_PROPERTY_KEY,
                    ATTR_ENDPOINT,
                    state.CONF_FROM,
                    state.CONF_TO,
                ],
            )
            event_config = event.TRIGGER_SCHEMA(event_config)
            # Get the device tracker for this device, creating a new one if it doesn't
            # exist
            device_tracker: DeviceTracker = hass.data[DOMAIN][config_entry_id][
                DATA_DEVICE_TRIGGER_TRACKERS
            ].setdefault(
                device_id,
                DeviceTracker(hass, config_entry_id, device_id, node),
            )
            # Get the value tracker for this value, creating a new one if it doesn't
            # exist
            value_tracker = device_tracker.values.setdefault(
                value.value_id,
                ValueTracker(device_tracker, value, value.value),
            )
            # Every time we attach, we assume we have to create an automation tracker
            # since the same automation shouldn't attach multiple times without
            # detaching in between
            automation_tracker = value_tracker.automations[
                automation_id
            ] = AutomationTracker(
                value_tracker,
                automation_id,
                await event.async_attach_trigger(
                    hass,
                    event_config,
                    action,
                    automation_info,
                    platform_type="device",
                ),
            )
            # Return our function as a detach trigger callback so that we can update
            # the device tracker, value tracker, and automation tracker
            LOGGER.debug("Attaching automation trigger: %s", event_config)
            return functools.partial(_detach_trigger, hass, automation_tracker)
        else:
            raise HomeAssistantError(f"Unhandled trigger type {trigger_type}")

        event_config = event.TRIGGER_SCHEMA(event_config)
        LOGGER.debug("Attaching automation trigger: %s", event_config)
        return await event.async_attach_trigger(
            hass, event_config, action, automation_info, platform_type="device"
        )

    # state triggers
    if trigger_platform == "state":
        state_config = {state.CONF_PLATFORM: "state"}

        if trigger_type == NODE_STATUS:
            state_config[state.CONF_ENTITY_ID] = config[CONF_ENTITY_ID]
            copy_available_params(
                config, state_config, [state.CONF_FOR, state.CONF_FROM, state.CONF_TO]
            )
        else:
            raise HomeAssistantError(f"Unhandled trigger type {trigger_type}")

        state_config = state.TRIGGER_SCHEMA(state_config)
        return await state.async_attach_trigger(
            hass, state_config, action, automation_info, platform_type="device"
        )

    raise HomeAssistantError(f"Unhandled trigger type {trigger_type}")


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    trigger_type = config[CONF_TYPE]

    node = async_get_node_from_device_id(hass, config[CONF_DEVICE_ID])
    value = (
        get_zwave_value_from_config(node, config) if ATTR_PROPERTY in config else None
    )

    # Add additional fields to the automation trigger UI
    if trigger_type == NOTIFICATION_NOTIFICATION:
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

    if trigger_type == ENTRY_CONTROL_NOTIFICATION:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(ATTR_EVENT_TYPE): cv.string,
                    vol.Optional(ATTR_DATA_TYPE): cv.string,
                }
            )
        }

    if trigger_type == NODE_STATUS:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(state.CONF_FROM): vol.In(NODE_STATUSES),
                    vol.Optional(state.CONF_TO): vol.In(NODE_STATUSES),
                    vol.Optional(state.CONF_FOR): cv.positive_time_period_dict,
                }
            )
        }

    if trigger_type in (
        BASIC_VALUE_NOTIFICATION,
        CENTRAL_SCENE_VALUE_NOTIFICATION,
        SCENE_ACTIVATION_VALUE_NOTIFICATION,
    ):
        if value.metadata.states:
            value_schema = vol.In({int(k): v for k, v in value.metadata.states.items()})
        else:
            value_schema = vol.All(
                vol.Coerce(int),
                vol.Range(min=value.metadata.min, max=value.metadata.max),
            )

        return {"extra_fields": vol.Schema({vol.Optional(ATTR_VALUE): value_schema})}

    if trigger_type == CONFIG_PARAMETER_VALUE_UPDATE:
        # We can be more deliberate about the config param schema here because there
        # are a limited number of types.
        if value.configuration_value_type == ConfigurationValueType.UNDEFINED:
            return {}
        if value.configuration_value_type == ConfigurationValueType.ENUMERATED:
            value_schema = vol.In({int(k): v for k, v in value.metadata.states.items()})
        else:
            value_schema = vol.All(
                vol.Coerce(int),
                vol.Range(min=value.metadata.min, max=value.metadata.max),
            )
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(state.CONF_FROM): value_schema,
                    vol.Optional(state.CONF_TO): value_schema,
                }
            )
        }

    if trigger_type == VALUE_VALUE_UPDATE:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND_CLASS): vol.In(
                        {cc.value: cc.name for cc in CommandClass}
                    ),
                    vol.Required(ATTR_PROPERTY): cv.string,
                    vol.Optional(ATTR_PROPERTY_KEY): cv.string,
                    vol.Optional(ATTR_ENDPOINT): cv.string,
                    vol.Optional(state.CONF_FROM): cv.string,
                    vol.Optional(state.CONF_TO): cv.string,
                }
            )
        }

    return {}
