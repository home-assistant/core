"""Provides device actions for Z-Wave JS."""
from __future__ import annotations

import voluptuous as vol
from zwave_js_server.const import ATTR_CODE_SLOT, ATTR_USERCODE, CommandClass
from zwave_js_server.model.value import get_value_id

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_ENTITY_ID, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_CONFIG_PARAMETER,
    ATTR_CONFIG_PARAMETER_BITMASK,
    ATTR_ENDPOINT,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_REFRESH_ALL_VALUES,
    ATTR_VALUE,
    ATTR_WAIT_FOR_RESULT,
    DOMAIN,
    SERVICE_PING,
    SERVICE_REFRESH_VALUE,
    SERVICE_SET_CONFIG_PARAMETER,
    SERVICE_SET_VALUE,
)
from .device_automation_helpers import VALUE_SCHEMA, get_config_parameter_value_schema
from .helpers import async_get_node_from_device_id
from .lock import SERVICE_CLEAR_LOCK_USERCODE, SERVICE_SET_LOCK_USERCODE

CONF_SUBTYPE = "subtype"

ACTION_TYPES = {
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_SET_LOCK_USERCODE,
    SERVICE_SET_VALUE,
    SERVICE_REFRESH_VALUE,
    SERVICE_PING,
    SERVICE_SET_CONFIG_PARAMETER,
}

CLEAR_LOCK_USERCODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_CLEAR_LOCK_USERCODE,
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(LOCK_DOMAIN),
        vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
    }
)

SET_LOCK_USERCODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_SET_LOCK_USERCODE,
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(LOCK_DOMAIN),
        vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
        vol.Required(ATTR_USERCODE): cv.string,
    }
)

REFRESH_VALUE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_REFRESH_VALUE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_REFRESH_ALL_VALUES, default=False): cv.boolean,
    }
)

PING_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_PING,
    }
)

SET_VALUE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_SET_VALUE,
        vol.Required(ATTR_COMMAND_CLASS): vol.In([cc.value for cc in CommandClass]),
        vol.Required(ATTR_PROPERTY): vol.Any(int, str),
        vol.Optional(ATTR_PROPERTY_KEY): vol.Any(vol.Coerce(int), cv.string),
        vol.Optional(ATTR_ENDPOINT): vol.Coerce(int),
        vol.Required(ATTR_VALUE): VALUE_SCHEMA,
        vol.Optional(ATTR_WAIT_FOR_RESULT, default=False): cv.boolean,
    }
)

SET_CONFIG_PARAMETER_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_SET_CONFIG_PARAMETER,
        vol.Required(ATTR_CONFIG_PARAMETER): vol.Any(int, str),
        vol.Required(ATTR_CONFIG_PARAMETER_BITMASK): vol.Any(None, int, str),
        vol.Required(ATTR_VALUE): vol.Coerce(int),
        vol.Required(CONF_SUBTYPE): cv.string,
    }
)

ACTION_SCHEMA = vol.Any(
    CLEAR_LOCK_USERCODE_SCHEMA,
    PING_SCHEMA,
    REFRESH_VALUE_SCHEMA,
    SET_CONFIG_PARAMETER_SCHEMA,
    SET_LOCK_USERCODE_SCHEMA,
    SET_VALUE_SCHEMA,
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device actions for Z-Wave JS devices."""
    registry = entity_registry.async_get(hass)
    actions = []

    node = async_get_node_from_device_id(hass, device_id)

    base_action = {
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    actions.extend(
        [
            {**base_action, CONF_TYPE: SERVICE_SET_VALUE},
            {**base_action, CONF_TYPE: SERVICE_PING},
        ]
    )
    actions.extend(
        [
            {
                **base_action,
                CONF_TYPE: SERVICE_SET_CONFIG_PARAMETER,
                ATTR_CONFIG_PARAMETER: config_value.property_,
                ATTR_CONFIG_PARAMETER_BITMASK: config_value.property_key,
                CONF_SUBTYPE: f"{config_value.value_id} ({config_value.property_name})",
            }
            for config_value in node.get_configuration_values().values()
        ]
    )

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        base_action[CONF_ENTITY_ID] = entry.entity_id
        if entry.domain == LOCK_DOMAIN:
            actions.extend(
                [
                    {**base_action, CONF_TYPE: SERVICE_SET_LOCK_USERCODE},
                    {**base_action, CONF_TYPE: SERVICE_CLEAR_LOCK_USERCODE},
                ]
            )

        actions.append({**base_action, CONF_TYPE: SERVICE_REFRESH_VALUE})

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    action_type = service = config.pop(CONF_TYPE)
    service_data = {k: v for k, v in config.items() if v not in (None, "")}

    if action_type not in ACTION_TYPES:
        raise HomeAssistantError(f"Unhandled action type {action_type}")

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    action_type = config[CONF_TYPE]
    node = async_get_node_from_device_id(hass, config[CONF_DEVICE_ID])

    # Add additional fields to the automation action UI
    if action_type == SERVICE_CLEAR_LOCK_USERCODE:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_CODE_SLOT): cv.string,
                }
            )
        }

    if action_type == SERVICE_SET_LOCK_USERCODE:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_CODE_SLOT): cv.string,
                    vol.Required(ATTR_USERCODE): cv.string,
                }
            )
        }

    if action_type == SERVICE_REFRESH_VALUE:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(ATTR_REFRESH_ALL_VALUES): cv.boolean,
                }
            )
        }

    if action_type == SERVICE_SET_VALUE:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND_CLASS): vol.In(
                        {cc.value: cc.name for cc in CommandClass}
                    ),
                    vol.Required(ATTR_PROPERTY): cv.string,
                    vol.Optional(ATTR_PROPERTY_KEY): cv.string,
                    vol.Optional(ATTR_ENDPOINT): cv.string,
                    vol.Required(ATTR_VALUE): cv.string,
                    vol.Optional(ATTR_WAIT_FOR_RESULT): cv.boolean,
                }
            )
        }

    if action_type == SERVICE_SET_CONFIG_PARAMETER:
        value_id = get_value_id(
            node,
            CommandClass.CONFIGURATION,
            config[ATTR_CONFIG_PARAMETER],
            property_key=config[ATTR_CONFIG_PARAMETER_BITMASK],
        )
        value_schema = get_config_parameter_value_schema(node, value_id)
        if value_schema is None:
            return {}
        return {"extra_fields": vol.Schema({vol.Required(ATTR_VALUE): value_schema})}

    return {}
