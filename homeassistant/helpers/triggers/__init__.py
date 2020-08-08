"""Triggers."""
import asyncio
import importlib
import logging
from typing import Any, Callable, List, Optional, cast

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.typing import ConfigType, HomeAssistantType


def _get_trigger_platform(config: ConfigType) -> Any:
    return importlib.import_module(f".{config[CONF_PLATFORM]}", __name__)


def trigger_platform_validator(config: ConfigType) -> ConfigType:
    """Validate it is a valid platform."""
    try:
        platform = _get_trigger_platform(config)
    except ImportError:
        raise vol.Invalid("Invalid platform specified") from None

    return cast(ConfigType, platform.TRIGGER_SCHEMA(config))


async def async_validate_trigger_config(
    hass: HomeAssistantType, trigger_config: List[ConfigType]
) -> List[ConfigType]:
    """Validate triggers."""
    config = []
    for conf in trigger_config:
        platform = _get_trigger_platform(conf)
        if hasattr(platform, "async_validate_trigger_config"):
            conf = await platform.async_validate_trigger_config(hass, conf)
        config.append(conf)
    return config


async def async_initialize_triggers(
    hass: HomeAssistantType,
    trigger_config: List[ConfigType],
    action: Callable,
    name: str,
    log_cb: Callable,
    home_assistant_start: bool = False,
) -> Optional[CALLBACK_TYPE]:
    """Initialize triggers."""
    info = {"name": name, "home_assistant_start": home_assistant_start}

    removes = await asyncio.gather(
        *[
            _get_trigger_platform(conf).async_attach_trigger(hass, conf, action, info)
            for conf in trigger_config
        ]
    )

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
