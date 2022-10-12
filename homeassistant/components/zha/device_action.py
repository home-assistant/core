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
from .api import SERVICE_WARNING_DEVICE_SQUAWK, SERVICE_WARNING_DEVICE_WARN
from .core.channels.manufacturerspecific import InovelliConfigEntityChannel
from .core.const import CHANNEL_IAS_WD, CHANNEL_INOVELLI
from .core.helpers import async_get_zha_device

# mypy: disallow-any-generics

ACTION_SQUAWK = "squawk"
ACTION_WARN = "warn"
ATTR_DATA = "data"
ATTR_IEEE = "ieee"
CONF_ZHA_ACTION_TYPE = "zha_action_type"
ZHA_ACTION_TYPE_SERVICE_CALL = "service_call"
ZHA_ACTION_TYPE_CHANNEL_COMMAND = "channel_command"
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
        vol.Required(
            "effect_type"
        ): InovelliConfigEntityChannel.LEDEffectType.__getitem__,
        vol.Required("color"): vol.All(vol.Coerce(int), vol.Range(0, 255)),
        vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
        vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(1, 255)),
    }
)

INOVELLI_INDIVIDUAL_LED_EFFECT_SCHEMA = INOVELLI_ALL_LED_EFFECT_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): INOVELLI_INDIVIDUAL_LED_EFFECT,
        vol.Required("led_number"): vol.All(vol.Coerce(int), vol.Range(1, 7)),
    }
)

ACTION_SCHEMA = vol.Any(
    INOVELLI_ALL_LED_EFFECT_SCHEMA,
    INOVELLI_INDIVIDUAL_LED_EFFECT_SCHEMA,
    DEFAULT_ACTION_SCHEMA,
)

DEVICE_ACTIONS = {
    CHANNEL_IAS_WD: [
        {CONF_TYPE: ACTION_SQUAWK, CONF_DOMAIN: DOMAIN},
        {CONF_TYPE: ACTION_WARN, CONF_DOMAIN: DOMAIN},
    ],
    CHANNEL_INOVELLI: [
        {CONF_TYPE: INOVELLI_ALL_LED_EFFECT, CONF_DOMAIN: DOMAIN},
        {CONF_TYPE: INOVELLI_INDIVIDUAL_LED_EFFECT, CONF_DOMAIN: DOMAIN},
    ],
}

DEVICE_ACTION_TYPES = {
    ACTION_SQUAWK: ZHA_ACTION_TYPE_SERVICE_CALL,
    ACTION_WARN: ZHA_ACTION_TYPE_SERVICE_CALL,
    INOVELLI_ALL_LED_EFFECT: ZHA_ACTION_TYPE_CHANNEL_COMMAND,
    INOVELLI_INDIVIDUAL_LED_EFFECT: ZHA_ACTION_TYPE_CHANNEL_COMMAND,
}

DEVICE_ACTION_SCHEMAS = {
    INOVELLI_ALL_LED_EFFECT: vol.Schema(
        {
            vol.Required("effect_type"): vol.In(
                InovelliConfigEntityChannel.LEDEffectType.__members__.keys()
            ),
            vol.Required("color"): vol.All(vol.Coerce(int), vol.Range(0, 255)),
            vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
            vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(1, 255)),
        }
    ),
    INOVELLI_INDIVIDUAL_LED_EFFECT: vol.Schema(
        {
            vol.Required("led_number"): vol.All(vol.Coerce(int), vol.Range(1, 7)),
            vol.Required("effect_type"): vol.In(
                InovelliConfigEntityChannel.LEDEffectType.__members__.keys()
            ),
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

CHANNEL_MAPPINGS = {
    INOVELLI_ALL_LED_EFFECT: CHANNEL_INOVELLI,
    INOVELLI_INDIVIDUAL_LED_EFFECT: CHANNEL_INOVELLI,
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


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions."""
    try:
        zha_device = async_get_zha_device(hass, device_id)
    except (KeyError, AttributeError):
        return []
    cluster_channels = [
        ch.name
        for pool in zha_device.channels.pools
        for ch in pool.claimed_channels.values()
    ]
    actions = [
        action
        for channel, channel_actions in DEVICE_ACTIONS.items()
        for action in channel_actions
        if channel in cluster_channels
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


async def _execute_channel_command_based_action(
    hass: HomeAssistant,
    config: dict[str, Any],
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    action_type = config[CONF_TYPE]
    channel_name = CHANNEL_MAPPINGS[action_type]
    try:
        zha_device = async_get_zha_device(hass, config[CONF_DEVICE_ID])
    except (KeyError, AttributeError):
        return

    action_channel = None
    for pool in zha_device.channels.pools:
        for channel in pool.all_channels.values():
            if channel.name == channel_name:
                action_channel = channel
                break

    if action_channel is None:
        raise InvalidDeviceAutomationConfig(
            f"Unable to execute channel action - channel: {channel_name} action: {action_type}"
        )

    if not hasattr(action_channel, action_type):
        raise InvalidDeviceAutomationConfig(
            f"Unable to execute channel action - channel: {channel_name} action: {action_type}"
        )

    await getattr(action_channel, action_type)(**config)


ZHA_ACTION_TYPES = {
    ZHA_ACTION_TYPE_SERVICE_CALL: _execute_service_based_action,
    ZHA_ACTION_TYPE_CHANNEL_COMMAND: _execute_channel_command_based_action,
}
