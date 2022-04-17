"""Helpers to help with integration platforms."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import Event, HomeAssistant
from homeassistant.loader import async_get_integration, bind_hass
from homeassistant.setup import ATTR_COMPONENT

_LOGGER = logging.getLogger(__name__)
DATA_INTEGRATION_PLATFORMS = "integration_platforms"


@dataclass(frozen=True)
class IntegrationPlatform:
    """An integration platform."""

    platform_name: str
    process_platform: Callable[[HomeAssistant, str, Any], Awaitable[None]]
    seen_components: set[str]


async def async_process_integration_platform(
    hass: HomeAssistant, component_name: str
) -> None:
    """Process component being loaded or on demand."""
    if "." in component_name:
        return

    integration = await async_get_integration(hass, component_name)

    integration_platforms: list[IntegrationPlatform] = hass.data[
        DATA_INTEGRATION_PLATFORMS
    ]
    for integration_platform in integration_platforms:
        platform_name = integration_platform.platform_name
        if component_name in integration_platform.seen_components:
            continue
        integration_platform.seen_components.add(component_name)

        try:
            platform = integration.get_platform(platform_name)
        except ImportError as err:
            if f"{component_name}.{platform_name}" not in str(err):
                _LOGGER.exception(
                    "Unexpected error importing %s/%s.py",
                    component_name,
                    platform_name,
                )
            continue

        try:
            await integration_platform.process_platform(hass, component_name, platform)  # type: ignore[misc,operator] # https://github.com/python/mypy/issues/5485
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error processing platform %s.%s", component_name, platform_name
            )


@bind_hass
async def async_process_integration_platforms(
    hass: HomeAssistant,
    platform_name: str,
    # Any = platform.
    process_platform: Callable[[HomeAssistant, str, Any], Awaitable[None]],
) -> None:
    """Process a specific platform for all current and future loaded integrations."""
    if DATA_INTEGRATION_PLATFORMS not in hass.data:
        hass.data[DATA_INTEGRATION_PLATFORMS] = []

        async def _async_component_loaded(event: Event) -> None:
            """Handle a new component loaded."""
            await async_process_integration_platform(hass, event.data[ATTR_COMPONENT])

        hass.bus.async_listen(EVENT_COMPONENT_LOADED, _async_component_loaded)

    integration_platforms: list[IntegrationPlatform] = hass.data[
        DATA_INTEGRATION_PLATFORMS
    ]
    integration_platforms.append(
        IntegrationPlatform(platform_name, process_platform, set())
    )

    if hass.config.components:
        await asyncio.gather(
            *[
                async_process_integration_platform(hass, comp)
                for comp in hass.config.components
            ]
        )
