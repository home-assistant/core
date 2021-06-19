"""Provide the device conditions for Z-Wave JS."""
from __future__ import annotations

from typing import cast

import voluptuous as vol
from zwave_js_server.const import ConfigurationValueType
from zwave_js_server.model.value import ConfigurationValue

from homeassistant.components.zwave_js.const import ATTR_VALUE
from homeassistant.const import CONF_CONDITION, CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN
from .helpers import async_get_node_from_device_id

CONF_SUBTYPE = "subtype"

CONF_VALUE_ID = "value_id"

NODE_STATUS_TYPES = {"asleep", "awake", "dead", "alive"}
CONFIG_PARAMETER_TYPE = "config_parameter"
CONDITION_TYPES = {*NODE_STATUS_TYPES, CONFIG_PARAMETER_TYPE}

NODE_STATUS_CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(NODE_STATUS_TYPES),
    }
)

CONFIG_PARAMETER_CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): CONFIG_PARAMETER_TYPE,
        vol.Required(CONF_VALUE_ID): cv.string,
        vol.Required(CONF_SUBTYPE): cv.string,
        vol.Optional(ATTR_VALUE): vol.Coerce(int),
    }
)

CONDITION_SCHEMA = vol.Any(
    NODE_STATUS_CONDITION_SCHEMA, CONFIG_PARAMETER_CONDITION_SCHEMA
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Z-Wave JS devices."""
    node = async_get_node_from_device_id(hass, device_id)

    base_condition = {
        CONF_CONDITION: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    # Node status conditions
    conditions = [{**base_condition, CONF_TYPE: cond} for cond in NODE_STATUS_TYPES]

    # Config parameter conditions
    conditions.extend(
        [
            {
                **base_condition,
                CONF_VALUE_ID: config_value.value_id,
                CONF_TYPE: CONFIG_PARAMETER_TYPE,
                CONF_SUBTYPE: f"{config_value.value_id} ({config_value.property_name})",
            }
            for config_value in node.get_configuration_values().values()
        ]
    )

    return conditions


@callback
def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config_validation:
        config = CONDITION_SCHEMA(config)

    condition_type = config[CONF_TYPE]
    device_id = config[CONF_DEVICE_ID]

    @callback
    def test_node_status(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if node status is a certain state."""
        node = async_get_node_from_device_id(hass, device_id)
        return bool(node.status.name.lower() == condition_type)

    if condition_type in NODE_STATUS_TYPES:
        return test_node_status

    value_id = config[CONF_VALUE_ID]
    value = config[ATTR_VALUE]

    @callback
    def test_config_parameter(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if config parameter is a certain state."""
        node = async_get_node_from_device_id(hass, device_id)
        config_value = cast(ConfigurationValue, node.values[value_id])
        return bool(config_value.value == value)

    return test_config_parameter


@callback
async def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""
    # Add additional fields to the automation trigger UI
    if config[CONF_TYPE] == CONFIG_PARAMETER_TYPE:
        device_id = config[CONF_DEVICE_ID]
        value_id = config[CONF_VALUE_ID]
        node = async_get_node_from_device_id(hass, device_id)
        config_value = cast(ConfigurationValue, node.values[value_id])

        if config_value.configuration_value_type in (
            ConfigurationValueType.RANGE,
            ConfigurationValueType.MANUAL_ENTRY,
        ):
            value_schema = vol.Range(
                min=config_value.metadata.min, max=config_value.metadata.max
            )
        elif config_value.configuration_value_type == ConfigurationValueType.ENUMERATED:
            value_schema = vol.In(
                {int(k): v for k, v in config_value.metadata.states.items()}
            )
        else:
            return {}

        return {"extra_fields": vol.Schema({vol.Required(ATTR_VALUE): value_schema})}

    return {}
