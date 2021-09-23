"""Provides device actions for Z-Wave JS."""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import ATTR_CODE_SLOT, ATTR_USERCODE
from zwave_js_server.const.command_class.meter import CC_SPECIFIC_METER_TYPE
from zwave_js_server.model.value import get_value_id
from zwave_js_server.util.command_class.meter import get_meter_type

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
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
    ATTR_METER_TYPE,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_REFRESH_ALL_VALUES,
    ATTR_VALUE,
    ATTR_WAIT_FOR_RESULT,
    DOMAIN,
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_PING,
    SERVICE_REFRESH_VALUE,
    SERVICE_RESET_METER,
    SERVICE_SET_CONFIG_PARAMETER,
    SERVICE_SET_LOCK_USERCODE,
    SERVICE_SET_VALUE,
    VALUE_SCHEMA,
)
from .device_automation_helpers import (
    CONF_SUBTYPE,
    VALUE_ID_REGEX,
    get_config_parameter_value_schema,
)
from .helpers import async_get_node_from_device_id

ACTION_TYPES = {
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_PING,
    SERVICE_REFRESH_VALUE,
    SERVICE_RESET_METER,
    SERVICE_SET_CONFIG_PARAMETER,
    SERVICE_SET_LOCK_USERCODE,
    SERVICE_SET_VALUE,
}

CLEAR_LOCK_USERCODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_CLEAR_LOCK_USERCODE,
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(LOCK_DOMAIN),
        vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
    }
)

PING_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_PING,
    }
)

REFRESH_VALUE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_REFRESH_VALUE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_REFRESH_ALL_VALUES, default=False): cv.boolean,
    }
)

RESET_METER_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_RESET_METER,
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(SENSOR_DOMAIN),
        vol.Optional(ATTR_METER_TYPE): vol.Coerce(int),
        vol.Optional(ATTR_VALUE): vol.Coerce(int),
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

SET_LOCK_USERCODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_SET_LOCK_USERCODE,
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(LOCK_DOMAIN),
        vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
        vol.Required(ATTR_USERCODE): cv.string,
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

ACTION_SCHEMA = vol.Any(
    CLEAR_LOCK_USERCODE_SCHEMA,
    PING_SCHEMA,
    REFRESH_VALUE_SCHEMA,
    RESET_METER_SCHEMA,
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

    meter_endpoints: dict[int, dict[str, Any]] = defaultdict(dict)

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        entity_action = {**base_action, CONF_ENTITY_ID: entry.entity_id}
        actions.append({**entity_action, CONF_TYPE: SERVICE_REFRESH_VALUE})
        if entry.domain == LOCK_DOMAIN:
            actions.extend(
                [
                    {**entity_action, CONF_TYPE: SERVICE_SET_LOCK_USERCODE},
                    {**entity_action, CONF_TYPE: SERVICE_CLEAR_LOCK_USERCODE},
                ]
            )

        if entry.domain == SENSOR_DOMAIN:
            value_id = entry.unique_id.split(".")[1]
            # If this unique ID doesn't have a value ID, we know it is the node status
            # sensor which doesn't have any relevant actions
            if re.match(VALUE_ID_REGEX, value_id):
                value = node.values[value_id]
            else:
                continue
            # If the value has the meterType CC specific value, we can add a reset_meter
            # action for it
            if CC_SPECIFIC_METER_TYPE in value.metadata.cc_specific:
                meter_endpoints[value.endpoint].setdefault(
                    CONF_ENTITY_ID, entry.entity_id
                )
                meter_endpoints[value.endpoint].setdefault(ATTR_METER_TYPE, set()).add(
                    get_meter_type(value)
                )

    if not meter_endpoints:
        return actions

    for endpoint, endpoint_data in meter_endpoints.items():
        base_action[CONF_ENTITY_ID] = endpoint_data[CONF_ENTITY_ID]
        actions.append(
            {
                **base_action,
                CONF_TYPE: SERVICE_RESET_METER,
                CONF_SUBTYPE: f"Endpoint {endpoint} (All)",
            }
        )
        for meter_type in endpoint_data[ATTR_METER_TYPE]:
            actions.append(
                {
                    **base_action,
                    CONF_TYPE: SERVICE_RESET_METER,
                    ATTR_METER_TYPE: meter_type,
                    CONF_SUBTYPE: f"Endpoint {endpoint} ({meter_type.name})",
                }
            )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    action_type = service = config.pop(CONF_TYPE)
    if action_type not in ACTION_TYPES:
        raise HomeAssistantError(f"Unhandled action type {action_type}")

    service_data = {k: v for k, v in config.items() if v not in (None, "")}
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

    if action_type == SERVICE_RESET_METER:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(ATTR_VALUE): cv.string,
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
