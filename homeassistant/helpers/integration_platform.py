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


async def _async_process_single_integration_platform_component(
    hass: HomeAssistant, component_name: str, integration_platform: IntegrationPlatform
) -> None:
    """Process a single integration platform."""
    if component_name in integration_platform.seen_components:
        return
    integration_platform.seen_components.add(component_name)

    integration = await async_get_integration(hass, component_name)
    platform_name = integration_platform.platform_name

    try:
        platform = integration.get_platform(platform_name)
    except ImportError as err:
        if f"{component_name}.{platform_name}" not in str(err):
            _LOGGER.exception(
                "Unexpected error importing %s/%s.py",
                component_name,
                platform_name,
            )
        return

    try:
        await integration_platform.process_platform(hass, component_name, platform)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception(
            "Error processing platform %s.%s", component_name, platform_name
        )


async def async_process_integration_platform_for_component(
    hass: HomeAssistant, component_name: str
) -> None:
    """Process integration platforms on demand for a component.

    This function will load the integration platforms
    for an integration instead of waiting for the EVENT_COMPONENT_LOADED
    event to be fired for the integration.

    When the integration will create entities before
    it has finished setting up; call this function to ensure
    that the integration platforms are loaded before the entities
    are created.
    """
    if DATA_INTEGRATION_PLATFORMS not in hass.data:
        # There are no integration platforms loaded yet
        return
    integration_platforms: list[IntegrationPlatform] = hass.data[
        DATA_INTEGRATION_PLATFORMS
    ]
    await asyncio.gather(
        *[
            _async_process_single_integration_platform_component(
                hass, component_name, integration_platform
            )
            for integration_platform in integration_platforms
        ]
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
            comp = event.data[ATTR_COMPONENT]
            if "." not in comp:
                await async_process_integration_platform_for_component(hass, comp)

        hass.bus.async_listen(EVENT_COMPONENT_LOADED, _async_component_loaded)

    integration_platforms: list[IntegrationPlatform] = hass.data[
        DATA_INTEGRATION_PLATFORMS
    ]
    integration_platform = IntegrationPlatform(platform_name, process_platform, set())
    integration_platforms.append(integration_platform)
    if top_level_components := (
        comp for comp in hass.config.components if "." not in comp
    ):
        await asyncio.gather(
            *[
                _async_process_single_integration_platform_component(
                    hass, comp, integration_platform
                )
                for comp in top_level_components
            ]
        )
