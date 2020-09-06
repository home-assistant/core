"""Config validation helper for the automation integration."""
import asyncio

import voluptuous as vol

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.condition import async_validate_condition_config
from homeassistant.helpers.script import async_validate_action_config
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.loader import IntegrationNotFound

from . import CONF_ACTION, CONF_CONDITION, CONF_TRIGGER, DOMAIN, PLATFORM_SCHEMA

# mypy: allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs, no-warn-return-any


async def async_validate_config_item(hass, config, full_config=None):
    """Validate config item."""
    config = PLATFORM_SCHEMA(config)

    config[CONF_TRIGGER] = await async_validate_trigger_config(
        hass, config[CONF_TRIGGER]
    )

    if CONF_CONDITION in config:
        config[CONF_CONDITION] = await asyncio.gather(
            *[
                async_validate_condition_config(hass, cond)
                for cond in config[CONF_CONDITION]
            ]
        )

    config[CONF_ACTION] = await asyncio.gather(
        *[async_validate_action_config(hass, action) for action in config[CONF_ACTION]]
    )

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
    automations = list(
        filter(
            lambda x: x is not None,
            await asyncio.gather(
                *(
                    _try_async_validate_config_item(hass, p_config, config)
                    for _, p_config in config_per_platform(config, DOMAIN)
                )
            ),
        )
    )

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, DOMAIN)
    config[DOMAIN] = automations

    return config
