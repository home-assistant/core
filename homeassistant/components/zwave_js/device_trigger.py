"""Provides device triggers for Z-Wave JS."""

import asyncio
from typing import Any

import probatio
from zwave_js_server.const import CommandClass

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import event, state
from homeassistant.components.homeassistant.triggers.event import EventTriggerArgument
from homeassistant.components.homeassistant.triggers.state import StateTriggerArgument
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .config_validation import COMMAND_CLASS_SCHEMA, VALUE_SCHEMA
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
    DOMAIN,
    NODE_STATUSES,
    ZWAVE_JS_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
)
from .device_automation_helpers import (
    CONF_SUBTYPE,
    async_bypass_dynamic_config_validation,
    generate_config_parameter_subtype,
)
from .helpers import (
    async_get_node_from_device_id,
    async_get_node_status_sensor_entity_id,
    copy_available_params,
    get_endpoint_indices_from_child_device,
    get_value_state_schema,
    get_zwave_value_from_config,
    remove_keys_with_empty_values,
)
from .triggers.value_updated import (
    ATTR_FROM,
    ATTR_TO,
    PLATFORM_TYPE as VALUE_UPDATED_PLATFORM_TYPE,
    async_attach_trigger as attach_value_updated_trigger,
    async_validate_trigger_config as validate_value_updated_trigger_config,
)

# Trigger types
ENTRY_CONTROL_NOTIFICATION = "event.notification.entry_control"
NOTIFICATION_NOTIFICATION = "event.notification.notification"
BASIC_VALUE_NOTIFICATION = "event.value_notification.basic"
CENTRAL_SCENE_VALUE_NOTIFICATION = "event.value_notification.central_scene"
SCENE_ACTIVATION_VALUE_NOTIFICATION = "event.value_notification.scene_activation"
CONFIG_PARAMETER_VALUE_UPDATED = f"{VALUE_UPDATED_PLATFORM_TYPE}.config_parameter"
VALUE_VALUE_UPDATED = f"{VALUE_UPDATED_PLATFORM_TYPE}.value"
NODE_STATUS = "state.node_status"


NOTIFICATION_EVENT_CC_MAPPINGS = (
    (ENTRY_CONTROL_NOTIFICATION, CommandClass.ENTRY_CONTROL),
    (NOTIFICATION_NOTIFICATION, CommandClass.NOTIFICATION),
)

# Event based trigger schemas
BASE_EVENT_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Required(ATTR_COMMAND_CLASS): COMMAND_CLASS_SCHEMA,
    }
)

NOTIFICATION_NOTIFICATION_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): NOTIFICATION_NOTIFICATION,
        probatio.Optional(f"{ATTR_TYPE}."): probatio.Coerce(int),
        probatio.Optional(ATTR_LABEL): cv.string,
        probatio.Optional(ATTR_EVENT): probatio.Coerce(int),
        probatio.Optional(ATTR_EVENT_LABEL): cv.string,
    }
)

ENTRY_CONTROL_NOTIFICATION_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): ENTRY_CONTROL_NOTIFICATION,
        probatio.Optional(ATTR_EVENT_TYPE): probatio.Coerce(int),
        probatio.Optional(ATTR_DATA_TYPE): probatio.Coerce(int),
    }
)

BASE_VALUE_NOTIFICATION_EVENT_SCHEMA = BASE_EVENT_SCHEMA.extend(
    {
        probatio.Required(ATTR_PROPERTY): probatio.Any(int, str),
        probatio.Optional(ATTR_PROPERTY_KEY): probatio.Any(int, str),
        probatio.Required(ATTR_ENDPOINT): probatio.Coerce(int),
        probatio.Optional(ATTR_VALUE): probatio.Coerce(int),
        probatio.Required(CONF_SUBTYPE): cv.string,
    }
)

BASIC_VALUE_NOTIFICATION_SCHEMA = BASE_VALUE_NOTIFICATION_EVENT_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): BASIC_VALUE_NOTIFICATION,
    }
)

CENTRAL_SCENE_VALUE_NOTIFICATION_SCHEMA = BASE_VALUE_NOTIFICATION_EVENT_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): CENTRAL_SCENE_VALUE_NOTIFICATION,
    }
)

SCENE_ACTIVATION_VALUE_NOTIFICATION_SCHEMA = (
    BASE_VALUE_NOTIFICATION_EVENT_SCHEMA.extend(
        {
            probatio.Required(CONF_TYPE): SCENE_ACTIVATION_VALUE_NOTIFICATION,
        }
    )
)

# State based trigger schemas
BASE_STATE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
    }
)

NODE_STATUS_SCHEMA = BASE_STATE_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): NODE_STATUS,
        probatio.Optional(StateTriggerArgument.FROM): probatio.In(NODE_STATUSES),
        probatio.Optional(StateTriggerArgument.TO): probatio.In(NODE_STATUSES),
        probatio.Optional(StateTriggerArgument.FOR): cv.positive_time_period_dict,
    }
)

# zwave_js.value_updated based trigger schemas
BASE_VALUE_UPDATED_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Required(ATTR_COMMAND_CLASS): COMMAND_CLASS_SCHEMA,
        probatio.Required(ATTR_PROPERTY): probatio.Any(int, str),
        probatio.Optional(ATTR_PROPERTY_KEY): probatio.Any(
            None, probatio.Coerce(int), str
        ),
        probatio.Optional(ATTR_ENDPOINT, default=0): probatio.Any(
            None, probatio.Coerce(int)
        ),
        probatio.Optional(ATTR_FROM): VALUE_SCHEMA,
        probatio.Optional(ATTR_TO): VALUE_SCHEMA,
    }
)

CONFIG_PARAMETER_VALUE_UPDATED_SCHEMA = BASE_VALUE_UPDATED_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): CONFIG_PARAMETER_VALUE_UPDATED,
        probatio.Required(CONF_SUBTYPE): cv.string,
    }
)

VALUE_VALUE_UPDATED_SCHEMA = BASE_VALUE_UPDATED_SCHEMA.extend(
    {
        probatio.Required(CONF_TYPE): VALUE_VALUE_UPDATED,
    }
)

TYPE_SCHEMA_MAP = {
    ENTRY_CONTROL_NOTIFICATION: ENTRY_CONTROL_NOTIFICATION_SCHEMA,
    NOTIFICATION_NOTIFICATION: NOTIFICATION_NOTIFICATION_SCHEMA,
    BASIC_VALUE_NOTIFICATION: BASIC_VALUE_NOTIFICATION_SCHEMA,
    CENTRAL_SCENE_VALUE_NOTIFICATION: CENTRAL_SCENE_VALUE_NOTIFICATION_SCHEMA,
    SCENE_ACTIVATION_VALUE_NOTIFICATION: SCENE_ACTIVATION_VALUE_NOTIFICATION_SCHEMA,
    CONFIG_PARAMETER_VALUE_UPDATED: CONFIG_PARAMETER_VALUE_UPDATED_SCHEMA,
    VALUE_VALUE_UPDATED: VALUE_VALUE_UPDATED_SCHEMA,
    NODE_STATUS: NODE_STATUS_SCHEMA,
}

TRIGGER_SCHEMA = probatio.All(
    remove_keys_with_empty_values,
    probatio.TaggedUnion(CONF_TYPE, TYPE_SCHEMA_MAP),
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = TRIGGER_SCHEMA(config)

    # We return early if the config entry for this device is not ready because we can't
    # validate the value without knowing the state of the device
    try:
        bypass_dynamic_config_validation = async_bypass_dynamic_config_validation(
            hass, config[CONF_DEVICE_ID]
        )
    except ValueError as err:
        raise InvalidDeviceAutomationConfig(
            f"Device {config[CONF_DEVICE_ID]} not found"
        ) from err

    if bypass_dynamic_config_validation:
        return config

    trigger_type = config[CONF_TYPE]
    if get_trigger_platform_from_type(trigger_type) == VALUE_UPDATED_PLATFORM_TYPE:
        try:
            node = async_get_node_from_device_id(hass, config[CONF_DEVICE_ID])
            get_zwave_value_from_config(node, config)
        except probatio.Invalid as err:
            raise InvalidDeviceAutomationConfig(err.msg) from err

        # On an endpoint child device, the configured endpoint must be one the child
        # covers. The capabilities form already pins this, but a manually authored
        # trigger would otherwise listen to an unrelated endpoint while reporting the
        # child device's id.
        device = dr.async_get(hass).async_get(config[CONF_DEVICE_ID])
        if (
            trigger_type == VALUE_VALUE_UPDATED
            and isinstance(device, dr.ChildDeviceEntry)
            and (endpoints := get_endpoint_indices_from_child_device(device, node))
            and config[ATTR_ENDPOINT] not in endpoints
        ):
            raise InvalidDeviceAutomationConfig(
                f"Endpoint {config[ATTR_ENDPOINT]} is not covered by device "
                f"{config[CONF_DEVICE_ID]}"
            )

    return config


def get_trigger_platform_from_type(trigger_type: str) -> str:
    """Get trigger platform from Z-Wave JS trigger type."""
    trigger_split = trigger_type.split(".")
    # Our convention for trigger types is to have the trigger type at the beginning
    # delimited by a `.`. For zwave_js triggers, there is a `.` in the name
    if (trigger_platform := trigger_split[0]) == DOMAIN:
        return ".".join(trigger_split[:2])
    return trigger_platform


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Z-Wave JS devices."""
    triggers: list[dict] = []
    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    dev_reg = dr.async_get(hass)
    node = async_get_node_from_device_id(hass, device_id)

    if node.client.driver and node.client.driver.controller.own_node == node:
        return triggers

    # Endpoint child devices only support the generic value-updated trigger. Node-based
    # event triggers (notifications, value notifications, node status) always fire with
    # the parent node's device_id, so they would never match a child device.
    if isinstance(dev_reg.async_get(device_id), dr.ChildDeviceEntry):
        triggers.append({**base_trigger, CONF_TYPE: VALUE_VALUE_UPDATED})
        return triggers

    # We can add a node status trigger if the node status sensor is enabled
    ent_reg = er.async_get(hass)
    entity_id = async_get_node_status_sensor_entity_id(
        hass, device_id, ent_reg, dev_reg
    )
    if (
        entity_id
        and (entity := ent_reg.async_get(entity_id)) is not None
        and not entity.disabled
    ):
        triggers.append(
            {**base_trigger, CONF_TYPE: NODE_STATUS, CONF_ENTITY_ID: entity.id}
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
    triggers.append({**base_trigger, CONF_TYPE: VALUE_VALUE_UPDATED})

    # Config parameter value update event triggers
    triggers.extend(
        [
            {
                **base_trigger,
                CONF_TYPE: CONFIG_PARAMETER_VALUE_UPDATED,
                ATTR_PROPERTY: config_value.property_,
                ATTR_PROPERTY_KEY: config_value.property_key,
                ATTR_ENDPOINT: config_value.endpoint,
                ATTR_COMMAND_CLASS: config_value.command_class,
                CONF_SUBTYPE: generate_config_parameter_subtype(config_value),
            }
            for config_value in node.get_configuration_values().values()
        ]
    )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trigger_type = config[CONF_TYPE]
    trigger_platform = get_trigger_platform_from_type(trigger_type)

    # Take input data from automation trigger UI and add it to the trigger we are
    # attaching to
    if trigger_platform == "event":
        event_data = {CONF_DEVICE_ID: config[CONF_DEVICE_ID]}
        event_config: ConfigType = {
            EventTriggerArgument.PLATFORM: "event",
            EventTriggerArgument.EVENT_DATA: event_data,
        }

        if ATTR_COMMAND_CLASS in config:
            event_data[ATTR_COMMAND_CLASS] = config[ATTR_COMMAND_CLASS]

        if trigger_type == ENTRY_CONTROL_NOTIFICATION:
            event_config[EventTriggerArgument.EVENT_TYPE] = ZWAVE_JS_NOTIFICATION_EVENT
            copy_available_params(config, event_data, [ATTR_EVENT_TYPE, ATTR_DATA_TYPE])
        elif trigger_type == NOTIFICATION_NOTIFICATION:
            event_config[EventTriggerArgument.EVENT_TYPE] = ZWAVE_JS_NOTIFICATION_EVENT
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
            event_config[EventTriggerArgument.EVENT_TYPE] = (
                ZWAVE_JS_VALUE_NOTIFICATION_EVENT
            )
            copy_available_params(
                config, event_data, [ATTR_PROPERTY, ATTR_PROPERTY_KEY, ATTR_ENDPOINT]
            )
            if ATTR_VALUE in config:
                event_data[ATTR_VALUE_RAW] = config[ATTR_VALUE]
        else:
            raise HomeAssistantError(f"Unhandled trigger type {trigger_type}")

        event_config = event.TRIGGER_SCHEMA(event_config)
        return await event.async_attach_trigger(
            hass, event_config, action, trigger_info, platform_type="device"
        )

    if trigger_platform == "state":
        if trigger_type == NODE_STATUS:
            state_config: ConfigType = {StateTriggerArgument.PLATFORM: "state"}

            state_config[StateTriggerArgument.ENTITY_ID] = config[CONF_ENTITY_ID]
            copy_available_params(
                config,
                state_config,
                [
                    StateTriggerArgument.FOR,
                    StateTriggerArgument.FROM,
                    StateTriggerArgument.TO,
                ],
            )
        else:
            raise HomeAssistantError(f"Unhandled trigger type {trigger_type}")

        state_config = await state.async_validate_trigger_config(hass, state_config)
        return await state.async_attach_trigger(
            hass, state_config, action, trigger_info, platform_type="device"
        )

    if trigger_platform == VALUE_UPDATED_PLATFORM_TYPE:
        zwave_js_config = {
            CONF_OPTIONS: {
                CONF_DEVICE_ID: config[CONF_DEVICE_ID],
            },
        }
        copy_available_params(
            config,
            zwave_js_config[CONF_OPTIONS],
            [
                ATTR_COMMAND_CLASS,
                ATTR_PROPERTY,
                ATTR_PROPERTY_KEY,
                ATTR_ENDPOINT,
                ATTR_FROM,
                ATTR_TO,
            ],
        )
        zwave_js_config = await validate_value_updated_trigger_config(
            hass, zwave_js_config
        )

        @callback
        def run_action(
            extra_trigger_payload: dict[str, Any],
            description: str,
            context: Context | None = None,
        ) -> asyncio.Task[Any]:
            """Run action with trigger variables."""

            payload = {
                "trigger": {
                    **trigger_info["trigger_data"],
                    CONF_PLATFORM: VALUE_UPDATED_PLATFORM_TYPE,
                    "description": description,
                    **extra_trigger_payload,
                }
            }

            return hass.async_create_task(action(payload, context))

        return await attach_value_updated_trigger(
            hass, zwave_js_config[CONF_OPTIONS], run_action
        )

    raise HomeAssistantError(f"Unhandled trigger type {trigger_type}")


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, probatio.Schema]:
    """List trigger capabilities."""
    trigger_type = config[CONF_TYPE]

    node = async_get_node_from_device_id(hass, config[CONF_DEVICE_ID])

    # Add additional fields to the automation trigger UI
    if trigger_type == NOTIFICATION_NOTIFICATION:
        return {
            "extra_fields": probatio.Schema(
                {
                    probatio.Optional(f"{ATTR_TYPE}."): cv.string,
                    probatio.Optional(ATTR_LABEL): cv.string,
                    probatio.Optional(ATTR_EVENT): cv.string,
                    probatio.Optional(ATTR_EVENT_LABEL): cv.string,
                }
            )
        }

    if trigger_type == ENTRY_CONTROL_NOTIFICATION:
        return {
            "extra_fields": probatio.Schema(
                {
                    probatio.Optional(ATTR_EVENT_TYPE): cv.string,
                    probatio.Optional(ATTR_DATA_TYPE): cv.string,
                }
            )
        }

    if trigger_type == NODE_STATUS:
        return {
            "extra_fields": probatio.Schema(
                {
                    probatio.Optional(StateTriggerArgument.FROM): probatio.In(
                        NODE_STATUSES
                    ),
                    probatio.Optional(StateTriggerArgument.TO): probatio.In(
                        NODE_STATUSES
                    ),
                    probatio.Optional(
                        StateTriggerArgument.FOR
                    ): cv.positive_time_period_dict,
                }
            )
        }

    if trigger_type in (
        BASIC_VALUE_NOTIFICATION,
        CENTRAL_SCENE_VALUE_NOTIFICATION,
        SCENE_ACTIVATION_VALUE_NOTIFICATION,
    ):
        value_schema = get_value_state_schema(get_zwave_value_from_config(node, config))

        # We should never get here, but just in case we should add a guard
        if not value_schema:
            return {}

        return {
            "extra_fields": probatio.Schema(
                {probatio.Optional(ATTR_VALUE): value_schema}
            )
        }

    if trigger_type == CONFIG_PARAMETER_VALUE_UPDATED:
        value_schema = get_value_state_schema(get_zwave_value_from_config(node, config))
        if not value_schema:
            return {}
        return {
            "extra_fields": probatio.Schema(
                {
                    probatio.Optional(ATTR_FROM): value_schema,
                    probatio.Optional(ATTR_TO): value_schema,
                }
            )
        }

    if trigger_type == VALUE_VALUE_UPDATED:
        # On an endpoint child device, restrict the command classes and endpoint to the
        # endpoint(s) the child covers, so a trigger created there matches the child's own
        # values and can't be retargeted at the node's root or an unrelated endpoint.
        device = dr.async_get(hass).async_get(config[CONF_DEVICE_ID])
        if isinstance(device, dr.ChildDeviceEntry) and (
            endpoints := get_endpoint_indices_from_child_device(device, node)
        ):
            command_classes = {
                command_class
                for endpoint in endpoints
                for command_class in node.endpoints[endpoint].command_classes
            }
            endpoint_field: Any = probatio.Required(ATTR_ENDPOINT)
            endpoint_schema: Any = probatio.In(
                [str(endpoint) for endpoint in endpoints]
            )
        else:
            command_classes = set(node.command_classes)
            endpoint_field = probatio.Optional(ATTR_ENDPOINT)
            endpoint_schema = cv.string
        # Exclude Configuration CC since it is already covered by its own trigger.
        extra_fields: dict[Any, Any] = {
            probatio.Required(ATTR_COMMAND_CLASS): probatio.In(
                {
                    str(CommandClass(cc.id).value): cc.name
                    for cc in sorted(command_classes, key=lambda cc: cc.name)
                    if cc.id != CommandClass.CONFIGURATION
                }
            ),
            probatio.Required(ATTR_PROPERTY): cv.string,
            probatio.Optional(ATTR_PROPERTY_KEY): cv.string,
            endpoint_field: endpoint_schema,
            probatio.Optional(ATTR_FROM): cv.string,
            probatio.Optional(ATTR_TO): cv.string,
        }
        return {"extra_fields": probatio.Schema(extra_fields)}

    return {}
