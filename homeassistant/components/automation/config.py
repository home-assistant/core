"""Config validation helper for the automation integration."""
import asyncio
import importlib
import logging

import voluptuous as vol

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.config import async_log_exception, config_without_domain
from homeassistant.const import CONF_ALIAS, CONF_ID, CONF_MODE, CONF_PLATFORM
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition, config_per_platform
from homeassistant.helpers.script import (
    SCRIPT_MODE_LEGACY,
    async_validate_action_config,
    warn_deprecated_legacy,
)
from homeassistant.loader import IntegrationNotFound

from . import CONF_ACTION, CONF_CONDITION, CONF_TRIGGER, DOMAIN, PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

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
        config[CONF_CONDITION] = await asyncio.gather(
            *[
                condition.async_validate_condition_config(hass, cond)
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


def _deprecated_legacy_mode(config):
    legacy_names = []
    legacy_unnamed_found = False

    for cfg in config[DOMAIN]:
        mode = cfg.get(CONF_MODE)
        if mode is None:
            cfg[CONF_MODE] = SCRIPT_MODE_LEGACY
            name = cfg.get(CONF_ID) or cfg.get(CONF_ALIAS)
            if name:
                legacy_names.append(name)
            else:
                legacy_unnamed_found = True

    if legacy_names or legacy_unnamed_found:
        msgs = []
        if legacy_unnamed_found:
            msgs.append("unnamed automations")
        if legacy_names:
            if len(legacy_names) == 1:
                base_msg = "this automation"
            else:
                base_msg = "these automations"
            msgs.append(f"{base_msg}: {', '.join(legacy_names)}")
        warn_deprecated_legacy(_LOGGER, " and ".join(msgs))

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

    _deprecated_legacy_mode(config)

    return config
