"""Helpers for the command_line integration."""

import asyncio
from collections.abc import Coroutine
from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, PLATFORM_MAPPING


async def async_load_platforms(
    hass: HomeAssistant,
    command_line_config: list[dict[str, dict[str, Any]]],
    config: ConfigType,
) -> None:
    """Load platforms from yaml."""
    if not command_line_config:
        return

    LOGGER.debug("Full config loaded: %s", command_line_config)

    load_coroutines: list[Coroutine[Any, Any, None]] = []
    platforms: list[Platform] = []
    reload_configs: list[tuple[Platform, dict[str, Any]]] = []
    for platform_config in command_line_config:
        for platform, _config in platform_config.items():
            if (mapped_platform := PLATFORM_MAPPING[platform]) not in platforms:
                platforms.append(mapped_platform)
            LOGGER.debug(
                "Loading config %s for platform %s",
                platform_config,
                PLATFORM_MAPPING[platform],
            )
            reload_configs.append((PLATFORM_MAPPING[platform], _config))
            load_coroutines.append(
                discovery.async_load_platform(
                    hass,
                    PLATFORM_MAPPING[platform],
                    DOMAIN,
                    _config,
                    config,
                )
            )

    if load_coroutines:
        LOGGER.debug("Loading platforms: %s", platforms)
        await asyncio.gather(*load_coroutines)
