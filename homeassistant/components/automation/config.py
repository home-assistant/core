"""Config validation helper for the automation integration."""
import asyncio
import importlib

import voluptuous as vol

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.const import CONF_PLATFORM
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition, config_per_platform, script
from homeassistant.loader import IntegrationNotFound

from . import CONF_ACTION, CONF_CONDITION, CONF_TRIGGER, DOMAIN, PLATFORM_SCHEMA

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any


async def async_validate_config_item(hass, config, full_config=None):
    """Validate config item."""
    config = PLATFORM_SCHEMA(config)

    triggers = []
    for trigger in config[CONF_TRIGGER]:
        trigger_platform = importlib.import_module(
            f"..{trigger[CONF_PLATFORM]}", __name__
        )
        if hasattr(trigger_platform, "async_validate_trigger_config"):
            trigger = await trigger_platform.async_validate_trigger_config(
                hass, trigger
            )
        triggers.append(trigger)
    config[CONF_TRIGGER] = triggers

    if CONF_CONDITION in config:
        conditions = []
        for cond in config[CONF_CONDITION]:
            cond = await condition.async_validate_condition_config(hass, cond)
            conditions.append(cond)
        config[CONF_CONDITION] = conditions

    actions = []
    for action in config[CONF_ACTION]:
        action = await script.async_validate_action_config(hass, action)
        actions.append(action)
    config[CONF_ACTION] = actions

    return config


async def _try_async_validate_config_item(hass, config, full_config=None):
    """Validate config item."""
    try:
        config = await async_validate_config_item(hass, config, full_config)
    except (
        vol.Invalid,
        HomeAssistantError,
        IntegrationNotFound,
        InvalidDeviceAutomationConfig,
    ) as ex:
        async_log_exception(ex, DOMAIN, full_config or config, hass)
        return None

    return config


async def async_validate_config(hass, config):
    """Validate config."""
    automations = []
    validated_automations = await asyncio.gather(
        *(
            _try_async_validate_config_item(hass, p_config, config)
            for _, p_config in config_per_platform(config, DOMAIN)
        )
    )
    for validated_automation in validated_automations:
        if validated_automation is not None:
            automations.append(validated_automation)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = automations

    return config
