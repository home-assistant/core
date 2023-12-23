"""Helpers to help with integration platforms."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.loader import Integration, async_get_integrations, bind_hass
from homeassistant.setup import ATTR_COMPONENT

_LOGGER = logging.getLogger(__name__)
DATA_INTEGRATION_PLATFORMS = "integration_platforms"


@dataclass(slots=True, frozen=True)
class IntegrationPlatform:
    """An integration platform."""

    platform_name: str
    process_platform: Callable[[HomeAssistant, str, Any], Awaitable[None]]
    seen_components: set[str]


async def _async_process_single_integration_platform_component(
    hass: HomeAssistant,
    component_name: str,
    integration: Integration | Exception,
    integration_platform: IntegrationPlatform,
) -> None:
    """Process a single integration platform."""
    if component_name in integration_platform.seen_components:
        return
    integration_platform.seen_components.add(component_name)

    if isinstance(integration, Exception):
        _LOGGER.exception(
            "Error importing integration %s for %s",
            component_name,
            integration_platform.platform_name,
        )
        return

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


async def _async_process_integration_platform_for_component(
    hass: HomeAssistant, component_name: str
) -> None:
    """Process integration platforms for a component."""
    integration_platforms: list[IntegrationPlatform] = hass.data[
        DATA_INTEGRATION_PLATFORMS
    ]
    integrations = await async_get_integrations(hass, (component_name,))
    tasks = [
        asyncio.create_task(
            _async_process_single_integration_platform_component(
                hass,
                component_name,
                integrations[component_name],
                integration_platform,
            ),
            name=f"process integration platform {integration_platform.platform_name} for {component_name}",
        )
        for integration_platform in integration_platforms
        if component_name not in integration_platform.seen_components
    ]
    if tasks:
        await asyncio.gather(*tasks)


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
            await _async_process_integration_platform_for_component(
                hass, event.data[ATTR_COMPONENT]
            )

        @callback
        def _async_component_loaded_filter(event: Event) -> bool:
            """Handle integration platforms loaded."""
            return "." not in event.data[ATTR_COMPONENT]

        hass.bus.async_listen(
            EVENT_COMPONENT_LOADED,
            _async_component_loaded,
            event_filter=_async_component_loaded_filter,
        )

    integration_platforms: list[IntegrationPlatform] = hass.data[
        DATA_INTEGRATION_PLATFORMS
    ]
    integration_platform = IntegrationPlatform(platform_name, process_platform, set())
    integration_platforms.append(integration_platform)
    if top_level_components := [
        comp for comp in hass.config.components if "." not in comp
    ]:
        integrations = await async_get_integrations(hass, top_level_components)
        tasks = [
            asyncio.create_task(
                _async_process_single_integration_platform_component(
                    hass, comp, integrations[comp], integration_platform
                ),
                name=f"process integration platform {platform_name} for {comp}",
            )
            for comp in top_level_components
            if comp not in integration_platform.seen_components
        ]
        if tasks:
            await asyncio.gather(*tasks)
