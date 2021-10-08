"""Triggers."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ID, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.loader import IntegrationNotFound, async_get_integration

_PLATFORM_ALIASES = {
    "device_automation": ("device",),
    "homeassistant": ("event", "numeric_state", "state", "time_pattern", "time"),
}


async def _async_get_trigger_platform(hass: HomeAssistant, config: ConfigType) -> Any:
    platform_and_sub_type = config[CONF_PLATFORM].split(".")
    platform = platform_and_sub_type[0]
    for alias, triggers in _PLATFORM_ALIASES.items():
        if platform in triggers:
            platform = alias
            break
    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise vol.Invalid(f"Invalid platform '{platform}' specified") from None
    try:
        return integration.get_platform("trigger")
    except ImportError:
        raise vol.Invalid(
            f"Integration '{platform}' does not provide trigger support"
        ) from None


async def async_validate_trigger_config(
    hass: HomeAssistant, trigger_config: list[ConfigType]
) -> list[ConfigType]:
    """Validate triggers."""
    config = []
    for conf in trigger_config:
        platform = await _async_get_trigger_platform(hass, conf)
        if hasattr(platform, "async_validate_trigger_config"):
            conf = await platform.async_validate_trigger_config(hass, conf)
        else:
            conf = platform.TRIGGER_SCHEMA(conf)
        config.append(conf)
    return config


async def async_initialize_triggers(
    hass: HomeAssistant,
    trigger_config: list[ConfigType],
    action: Callable,
    domain: str,
    name: str,
    log_cb: Callable,
    home_assistant_start: bool = False,
    variables: TemplateVarsType = None,
) -> CALLBACK_TYPE | None:
    """Initialize triggers."""

    triggers = []
    for idx, conf in enumerate(trigger_config):
        platform = await _async_get_trigger_platform(hass, conf)
        trigger_id = conf.get(CONF_ID, f"{idx}")
        trigger_idx = f"{idx}"
        trigger_data = {"id": trigger_id, "idx": trigger_idx}
        info = {
            "domain": domain,
            "name": name,
            "home_assistant_start": home_assistant_start,
            "variables": variables,
            "trigger_data": trigger_data,
        }
        triggers.append(platform.async_attach_trigger(hass, conf, action, info))

    attach_results = await asyncio.gather(*triggers, return_exceptions=True)
    removes = []

    for result in attach_results:
        if isinstance(result, HomeAssistantError):
            log_cb(logging.ERROR, f"Got error '{result}' when setting up triggers for")
        elif isinstance(result, Exception):
            log_cb(logging.ERROR, "Error setting up trigger", exc_info=result)
        elif result is None:
            log_cb(
                logging.ERROR, "Unknown error while setting up trigger (empty result)"
            )
        else:
            removes.append(result)

    if not removes:
        return None

    log_cb(logging.INFO, "Initialized trigger")

    @callback
    def remove_triggers():  # type: ignore
        """Remove triggers."""
        for remove in removes:
            remove()

    return remove_triggers
