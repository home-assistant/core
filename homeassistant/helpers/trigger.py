"""Triggers."""
import asyncio
import logging
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Optional, Union

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import IntegrationNotFound, async_get_integration

_PLATFORM_ALIASES = {
    "device_automation": ("device",),
    "homeassistant": ("event", "numeric_state", "state", "time_pattern", "time"),
}


async def _async_get_trigger_platform(
    hass: HomeAssistantType, config: ConfigType
) -> Any:
    platform = config[CONF_PLATFORM]
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
    hass: HomeAssistantType, trigger_config: List[ConfigType]
) -> List[ConfigType]:
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
    hass: HomeAssistantType,
    trigger_config: List[ConfigType],
    action: Callable,
    domain: str,
    name: str,
    log_cb: Callable,
    home_assistant_start: bool = False,
    variables: Optional[Union[Dict[str, Any], MappingProxyType]] = None,
) -> Optional[CALLBACK_TYPE]:
    """Initialize triggers."""
    info = {
        "domain": domain,
        "name": name,
        "home_assistant_start": home_assistant_start,
        "variables": variables,
    }

    triggers = []
    for conf in trigger_config:
        platform = await _async_get_trigger_platform(hass, conf)
        triggers.append(platform.async_attach_trigger(hass, conf, action, info))

    removes = await asyncio.gather(*triggers)

    if None in removes:
        log_cb(logging.ERROR, "Error setting up trigger")

    removes = list(filter(None, removes))
    if not removes:
        return None

    log_cb(logging.INFO, "Initialized trigger")

    @callback
    def remove_triggers():  # type: ignore
        """Remove triggers."""
        for remove in removes:
            remove()

    return remove_triggers
