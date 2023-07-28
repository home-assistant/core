"""Provides device actions for Z-Wave JS."""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import ATTR_CODE_SLOT, ATTR_USERCODE
from zwave_js_server.const.command_class.meter import CC_SPECIFIC_METER_TYPE
from zwave_js_server.model.value import get_value_id_str
from zwave_js_server.util.command_class.meter import get_meter_type

from homeassistant.components.device_automation import async_validate_entity_schema
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_DOMAIN,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .config_validation import VALUE_SCHEMA
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
)
from .device_automation_helpers import (
    CONF_SUBTYPE,
    VALUE_ID_REGEX,
    generate_config_parameter_subtype,
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
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
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
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Optional(ATTR_REFRESH_ALL_VALUES, default=False): cv.boolean,
    }
)

RESET_METER_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_RESET_METER,
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Optional(ATTR_METER_TYPE): vol.Coerce(int),
        vol.Optional(ATTR_VALUE): vol.Coerce(int),
    }
)

SET_CONFIG_PARAMETER_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_SET_CONFIG_PARAMETER,
        vol.Required(ATTR_ENDPOINT, default=0): vol.Coerce(int),
        vol.Required(ATTR_CONFIG_PARAMETER): vol.Any(int, str),
        vol.Required(ATTR_CONFIG_PARAMETER_BITMASK): vol.Any(None, int, str),
        vol.Required(ATTR_VALUE): vol.Coerce(int),
        vol.Required(CONF_SUBTYPE): cv.string,
    }
)

SET_LOCK_USERCODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): SERVICE_SET_LOCK_USERCODE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
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

_ACTION_SCHEMA = vol.Any(
    CLEAR_LOCK_USERCODE_SCHEMA,
    PING_SCHEMA,
    REFRESH_VALUE_SCHEMA,
    RESET_METER_SCHEMA,
    SET_CONFIG_PARAMETER_SCHEMA,
    SET_LOCK_USERCODE_SCHEMA,
    SET_VALUE_SCHEMA,
)


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    return async_validate_entity_schema(hass, config, _ACTION_SCHEMA)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device actions for Z-Wave JS devices."""
    registry = er.async_get(hass)
    actions: list[dict] = []

    node = async_get_node_from_device_id(hass, device_id)

    if node.client.driver and node.client.driver.controller.own_node == node:
        return actions

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
                ATTR_ENDPOINT: config_value.endpoint,
                ATTR_CONFIG_PARAMETER: config_value.property_,
                ATTR_CONFIG_PARAMETER_BITMASK: config_value.property_key,
                CONF_SUBTYPE: generate_config_parameter_subtype(config_value),
            }
            for config_value in node.get_configuration_values().values()
        ]
    )

    meter_endpoints: dict[int, dict[str, Any]] = defaultdict(dict)

    for entry in er.async_entries_for_device(
        registry, device_id, include_disabled_entities=False
    ):
        # If an entry is unavailable, it is possible that the underlying value
        # is no longer valid. Additionally, if an entry is disabled, its
        # underlying value is not being monitored by HA so we shouldn't allow
        # actions against it.
        if (
            not (state := hass.states.get(entry.entity_id))
            or state.state == STATE_UNAVAILABLE
        ):
            continue
        entity_action = {**base_action, CONF_ENTITY_ID: entry.id}
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
            if not re.match(VALUE_ID_REGEX, value_id):
                continue
            value = node.values[value_id]
            # If the value has the meterType CC specific value, we can add a reset_meter
            # action for it
            if CC_SPECIFIC_METER_TYPE in value.metadata.cc_specific:
                endpoint_idx = value.endpoint or 0
                meter_endpoints[endpoint_idx].setdefault(CONF_ENTITY_ID, entry.id)
                meter_endpoints[endpoint_idx].setdefault(ATTR_METER_TYPE, set()).add(
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
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    action_type = service = config[CONF_TYPE]
    if action_type not in ACTION_TYPES:
        raise HomeAssistantError(f"Unhandled action type {action_type}")

    # Don't include domain, subtype or any null/empty values in the service call
    service_data = {
        k: v
        for k, v in config.items()
        if k not in (ATTR_DOMAIN, CONF_TYPE, CONF_SUBTYPE) and v not in (None, "")
    }

    # Entity services (including refresh value which is a fake entity service) expect
    # just an entity ID
    if action_type in (
        SERVICE_REFRESH_VALUE,
        SERVICE_SET_LOCK_USERCODE,
        SERVICE_CLEAR_LOCK_USERCODE,
        SERVICE_RESET_METER,
    ):
        service_data.pop(ATTR_DEVICE_ID)
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
                        {
                            CommandClass(cc.id).value: cc.name
                            for cc in sorted(
                                node.command_classes, key=lambda cc: cc.name
                            )
                        }
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
        value_id = get_value_id_str(
            node,
            CommandClass.CONFIGURATION,
            config[ATTR_CONFIG_PARAMETER],
            property_key=config[ATTR_CONFIG_PARAMETER_BITMASK],
            endpoint=config[ATTR_ENDPOINT],
        )
        value_schema = get_config_parameter_value_schema(node, value_id)
        if value_schema is None:
            return {}
        return {"extra_fields": vol.Schema({vol.Required(ATTR_VALUE): value_schema})}

    return {}
