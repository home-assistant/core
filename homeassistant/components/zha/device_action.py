"""Provides device actions for ZHA devices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN
from .core.cluster_handlers.manufacturerspecific import (
    AllLEDEffectType,
    SingleLEDEffectType,
)
from .core.const import CLUSTER_HANDLER_IAS_WD, CLUSTER_HANDLER_INOVELLI
from .core.helpers import async_get_zha_device
from .websocket_api import SERVICE_WARNING_DEVICE_SQUAWK, SERVICE_WARNING_DEVICE_WARN

# mypy: disallow-any-generics

ACTION_SQUAWK = "squawk"
ACTION_WARN = "warn"
ATTR_DATA = "data"
ATTR_IEEE = "ieee"
CONF_ZHA_ACTION_TYPE = "zha_action_type"
ZHA_ACTION_TYPE_SERVICE_CALL = "service_call"
ZHA_ACTION_TYPE_CLUSTER_HANDLER_COMMAND = "cluster_handler_command"
INOVELLI_ALL_LED_EFFECT = "issue_all_led_effect"
INOVELLI_INDIVIDUAL_LED_EFFECT = "issue_individual_led_effect"

DEFAULT_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_TYPE): vol.In({ACTION_SQUAWK, ACTION_WARN}),
    }
)

INOVELLI_ALL_LED_EFFECT_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): INOVELLI_ALL_LED_EFFECT,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required("effect_type"): AllLEDEffectType.__getitem__,
        vol.Required("color"): vol.All(vol.Coerce(int), vol.Range(0, 255)),
        vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
        vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(1, 255)),
    }
)

INOVELLI_INDIVIDUAL_LED_EFFECT_SCHEMA = INOVELLI_ALL_LED_EFFECT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): INOVELLI_INDIVIDUAL_LED_EFFECT,
        vol.Required("effect_type"): SingleLEDEffectType.__getitem__,
        vol.Required("led_number"): vol.All(vol.Coerce(int), vol.Range(0, 6)),
    }
)

ACTION_SCHEMA_MAP = {
    INOVELLI_ALL_LED_EFFECT: INOVELLI_ALL_LED_EFFECT_SCHEMA,
    INOVELLI_INDIVIDUAL_LED_EFFECT: INOVELLI_INDIVIDUAL_LED_EFFECT_SCHEMA,
}

ACTION_SCHEMA = vol.Any(
    INOVELLI_ALL_LED_EFFECT_SCHEMA,
    INOVELLI_INDIVIDUAL_LED_EFFECT_SCHEMA,
    DEFAULT_ACTION_SCHEMA,
)

DEVICE_ACTIONS = {
    CLUSTER_HANDLER_IAS_WD: [
        {CONF_TYPE: ACTION_SQUAWK, CONF_DOMAIN: DOMAIN},
        {CONF_TYPE: ACTION_WARN, CONF_DOMAIN: DOMAIN},
    ],
    CLUSTER_HANDLER_INOVELLI: [
        {CONF_TYPE: INOVELLI_ALL_LED_EFFECT, CONF_DOMAIN: DOMAIN},
        {CONF_TYPE: INOVELLI_INDIVIDUAL_LED_EFFECT, CONF_DOMAIN: DOMAIN},
    ],
}

DEVICE_ACTION_TYPES = {
    ACTION_SQUAWK: ZHA_ACTION_TYPE_SERVICE_CALL,
    ACTION_WARN: ZHA_ACTION_TYPE_SERVICE_CALL,
    INOVELLI_ALL_LED_EFFECT: ZHA_ACTION_TYPE_CLUSTER_HANDLER_COMMAND,
    INOVELLI_INDIVIDUAL_LED_EFFECT: ZHA_ACTION_TYPE_CLUSTER_HANDLER_COMMAND,
}

DEVICE_ACTION_SCHEMAS = {
    INOVELLI_ALL_LED_EFFECT: vol.Schema(
        {
            vol.Required("effect_type"): vol.In(AllLEDEffectType.__members__.keys()),
            vol.Required("color"): vol.All(vol.Coerce(int), vol.Range(0, 255)),
            vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(1, 255)),
        }
    ),
    INOVELLI_INDIVIDUAL_LED_EFFECT: vol.Schema(
        {
            vol.Required("led_number"): vol.All(vol.Coerce(int), vol.Range(0, 6)),
            vol.Required("effect_type"): vol.In(SingleLEDEffectType.__members__.keys()),
            vol.Required("color"): vol.All(vol.Coerce(int), vol.Range(0, 255)),
            vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(1, 255)),
        }
    ),
}

SERVICE_NAMES = {
    ACTION_SQUAWK: SERVICE_WARNING_DEVICE_SQUAWK,
    ACTION_WARN: SERVICE_WARNING_DEVICE_WARN,
}

CLUSTER_HANDLER_MAPPINGS = {
    INOVELLI_ALL_LED_EFFECT: CLUSTER_HANDLER_INOVELLI,
    INOVELLI_INDIVIDUAL_LED_EFFECT: CLUSTER_HANDLER_INOVELLI,
}


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Perform an action based on configuration."""
    await ZHA_ACTION_TYPES[DEVICE_ACTION_TYPES[config[CONF_TYPE]]](
        hass, config, variables, context
    )


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    schema = ACTION_SCHEMA_MAP.get(config[CONF_TYPE], DEFAULT_ACTION_SCHEMA)
    return schema(config)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions."""
    try:
        zha_device = async_get_zha_device(hass, device_id)
    except (KeyError, AttributeError):
        return []
    cluster_handlers = [
        ch.name
        for endpoint in zha_device.endpoints.values()
        for ch in endpoint.claimed_cluster_handlers.values()
    ]
    actions = [
        action
        for cluster_handler, cluster_handler_actions in DEVICE_ACTIONS.items()
        for action in cluster_handler_actions
        if cluster_handler in cluster_handlers
    ]
    for action in actions:
        action[CONF_DEVICE_ID] = device_id
    return actions


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""

    return {"extra_fields": DEVICE_ACTION_SCHEMAS.get(config[CONF_TYPE], {})}


async def _execute_service_based_action(
    hass: HomeAssistant,
    config: dict[str, Any],
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    action_type = config[CONF_TYPE]
    service_name = SERVICE_NAMES[action_type]
    try:
        zha_device = async_get_zha_device(hass, config[CONF_DEVICE_ID])
    except (KeyError, AttributeError):
        return

    service_data = {ATTR_IEEE: str(zha_device.ieee)}

    await hass.services.async_call(
        DOMAIN, service_name, service_data, blocking=True, context=context
    )


async def _execute_cluster_handler_command_based_action(
    hass: HomeAssistant,
    config: dict[str, Any],
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    action_type = config[CONF_TYPE]
    cluster_handler_name = CLUSTER_HANDLER_MAPPINGS[action_type]
    try:
        zha_device = async_get_zha_device(hass, config[CONF_DEVICE_ID])
    except (KeyError, AttributeError):
        return

    action_cluster_handler = None
    for endpoint in zha_device.endpoints.values():
        for cluster_handler in endpoint.all_cluster_handlers.values():
            if cluster_handler.name == cluster_handler_name:
                action_cluster_handler = cluster_handler
                break

    if action_cluster_handler is None:
        raise InvalidDeviceAutomationConfig(
            f"Unable to execute cluster handler action - cluster handler: {cluster_handler_name} action:"
            f" {action_type}"
        )

    if not hasattr(action_cluster_handler, action_type):
        raise InvalidDeviceAutomationConfig(
            f"Unable to execute cluster handler - cluster handler: {cluster_handler_name} action:"
            f" {action_type}"
        )

    await getattr(action_cluster_handler, action_type)(**config)


ZHA_ACTION_TYPES = {
    ZHA_ACTION_TYPE_SERVICE_CALL: _execute_service_based_action,
    ZHA_ACTION_TYPE_CLUSTER_HANDLER_COMMAND: _execute_cluster_handler_command_based_action,
}
