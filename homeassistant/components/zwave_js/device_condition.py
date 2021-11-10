"""Provide the device conditions for Z-Wave JS."""
from __future__ import annotations

from typing import cast

import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.model.value import ConfigurationValue

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_CONDITION, CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN
from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_ENDPOINT,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_VALUE,
    VALUE_SCHEMA,
)
from .device_automation_helpers import (
    CONF_SUBTYPE,
    CONF_VALUE_ID,
    NODE_STATUSES,
    get_config_parameter_value_schema,
)
from .helpers import (
    async_get_node_from_device_id,
    async_is_device_config_entry_not_loaded,
    check_type_schema_map,
    get_zwave_value_from_config,
    remove_keys_with_empty_values,
)

CONF_STATUS = "status"

NODE_STATUS_TYPE = "node_status"
CONFIG_PARAMETER_TYPE = "config_parameter"
VALUE_TYPE = "value"
CONDITION_TYPES = {NODE_STATUS_TYPE, CONFIG_PARAMETER_TYPE, VALUE_TYPE}

NODE_STATUS_CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): NODE_STATUS_TYPE,
        vol.Required(CONF_STATUS): vol.In(NODE_STATUSES),
    }
)

CONFIG_PARAMETER_CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): CONFIG_PARAMETER_TYPE,
        vol.Required(CONF_VALUE_ID): cv.string,
        vol.Required(CONF_SUBTYPE): cv.string,
        vol.Optional(ATTR_VALUE): vol.Coerce(int),
    }
)

VALUE_CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): VALUE_TYPE,
        vol.Required(ATTR_COMMAND_CLASS): vol.In([cc.value for cc in CommandClass]),
        vol.Required(ATTR_PROPERTY): vol.Any(vol.Coerce(int), cv.string),
        vol.Optional(ATTR_PROPERTY_KEY): vol.Any(vol.Coerce(int), cv.string),
        vol.Optional(ATTR_ENDPOINT): vol.Coerce(int),
        vol.Required(ATTR_VALUE): VALUE_SCHEMA,
    }
)

TYPE_SCHEMA_MAP = {
    NODE_STATUS_TYPE: NODE_STATUS_CONDITION_SCHEMA,
    CONFIG_PARAMETER_TYPE: CONFIG_PARAMETER_CONDITION_SCHEMA,
    VALUE_TYPE: VALUE_CONDITION_SCHEMA,
}


CONDITION_TYPE_SCHEMA = vol.Schema(
    {vol.Required(CONF_TYPE): vol.In(TYPE_SCHEMA_MAP)}, extra=vol.ALLOW_EXTRA
)

CONDITION_SCHEMA = vol.All(
    remove_keys_with_empty_values,
    CONDITION_TYPE_SCHEMA,
    check_type_schema_map(TYPE_SCHEMA_MAP),
)


async def async_validate_condition_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = CONDITION_SCHEMA(config)

    # We return early if the config entry for this device is not ready because we can't
    # validate the value without knowing the state of the device
    if async_is_device_config_entry_not_loaded(hass, config[CONF_DEVICE_ID]):
        return config

    if config[CONF_TYPE] == VALUE_TYPE:
        try:
            node = async_get_node_from_device_id(hass, config[CONF_DEVICE_ID])
            get_zwave_value_from_config(node, config)
        except vol.Invalid as err:
            raise InvalidDeviceAutomationConfig(err.msg) from err

    return config


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Z-Wave JS devices."""
    conditions = []
    base_condition = {
        CONF_CONDITION: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }
    node = async_get_node_from_device_id(hass, device_id)

    # Any value's value condition
    conditions.append({**base_condition, CONF_TYPE: VALUE_TYPE})

    # Node status conditions
    conditions.append({**base_condition, CONF_TYPE: NODE_STATUS_TYPE})

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
        return bool(node.status.name.lower() == config[CONF_STATUS])

    if condition_type == NODE_STATUS_TYPE:
        return test_node_status

    @callback
    def test_config_parameter(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if config parameter is a certain state."""
        node = async_get_node_from_device_id(hass, device_id)
        config_value = cast(ConfigurationValue, node.values[config[CONF_VALUE_ID]])
        return bool(config_value.value == config[ATTR_VALUE])

    if condition_type == CONFIG_PARAMETER_TYPE:
        return test_config_parameter

    @callback
    def test_value(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if value is a certain state."""
        node = async_get_node_from_device_id(hass, device_id)
        value = get_zwave_value_from_config(node, config)
        return bool(value.value == config[ATTR_VALUE])

    if condition_type == VALUE_TYPE:
        return test_value

    raise HomeAssistantError(f"Unhandled condition type {condition_type}")


@callback
async def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""
    device_id = config[CONF_DEVICE_ID]
    node = async_get_node_from_device_id(hass, device_id)

    # Add additional fields to the automation trigger UI
    if config[CONF_TYPE] == CONFIG_PARAMETER_TYPE:
        value_id = config[CONF_VALUE_ID]
        value_schema = get_config_parameter_value_schema(node, value_id)
        if value_schema is None:
            return {}
        return {"extra_fields": vol.Schema({vol.Required(ATTR_VALUE): value_schema})}

    if config[CONF_TYPE] == VALUE_TYPE:
        # Only show command classes on this node and exclude Configuration CC since it
        # is already covered
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND_CLASS): vol.In(
                        {
                            CommandClass(cc.id).value: cc.name
                            for cc in sorted(node.command_classes, key=lambda cc: cc.name)  # type: ignore[no-any-return]
                            if cc.id != CommandClass.CONFIGURATION
                        }
                    ),
                    vol.Required(ATTR_PROPERTY): cv.string,
                    vol.Optional(ATTR_PROPERTY_KEY): cv.string,
                    vol.Optional(ATTR_ENDPOINT): cv.string,
                    vol.Required(ATTR_VALUE): cv.string,
                }
            )
        }

    if config[CONF_TYPE] == NODE_STATUS_TYPE:
        return {
            "extra_fields": vol.Schema(
                {vol.Required(CONF_STATUS): vol.In(NODE_STATUSES)}
            )
        }

    return {}
