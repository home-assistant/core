"""Helpers to help with integration platforms."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
import logging
from types import ModuleType
from typing import Any

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import Event, HassJob, HomeAssistant, callback
from homeassistant.loader import (
    Integration,
    async_get_integrations,
    async_get_loaded_integration,
    bind_hass,
)
from homeassistant.setup import ATTR_COMPONENT

_LOGGER = logging.getLogger(__name__)
DATA_INTEGRATION_PLATFORMS = "integration_platforms"


@dataclass(slots=True, frozen=True)
class IntegrationPlatform:
    """An integration platform."""

    platform_name: str
    process_platform: HassJob
    seen_components: set[str]


@callback
def _async_process_single_integration_platform_component(
    hass: HomeAssistant,
    component_name: str,
    platform: ModuleType,
    integration_platform: IntegrationPlatform,
) -> asyncio.Future[None] | None:
    """Process a single integration platform."""
    try:
        return hass.async_run_hass_job(
            integration_platform.process_platform, hass, component_name, platform
        )
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception(
            "Error processing platform %s.%s",
            component_name,
            integration_platform.platform_name,
        )
    return None


def _get_platform_from_integration(
    integration: Integration | Exception, component_name: str, platform_name: str
) -> ModuleType | None:
    """Get a platform from an integration."""
    if isinstance(integration, Exception):
        _LOGGER.exception(
            "Error importing integration %s for %s",
            component_name,
            platform_name,
        )
        return None

    try:
        return integration.get_platform(platform_name)
    except ImportError as err:
        if f"{component_name}.{platform_name}" not in str(err):
            _LOGGER.exception(
                "Unexpected error importing %s/%s.py",
                component_name,
                platform_name,
            )

    return None


@callback
def _async_process_integration_platform_for_component(
    hass: HomeAssistant, event: Event
) -> None:
    """Process integration platforms for a component."""
    component_name: str = event.data[ATTR_COMPONENT]
    if "." in component_name:
        return

    integration_platforms: list[IntegrationPlatform] = hass.data[
        DATA_INTEGRATION_PLATFORMS
    ]
    integration = async_get_loaded_integration(hass, component_name)
    for integration_platform in integration_platforms:
        if component_name in integration_platform.seen_components or not (
            platform := _get_platform_from_integration(
                integration, component_name, integration_platform.platform_name
            )
        ):
            continue
        integration_platform.seen_components.add(component_name)
        _async_process_single_integration_platform_component(
            hass, component_name, platform, integration_platform
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
        hass.bus.async_listen(
            EVENT_COMPONENT_LOADED,
            partial(_async_process_integration_platform_for_component, hass),
        )

    top_level_components = {comp for comp in hass.config.components if "." not in comp}
    if not top_level_components:
        return

    integrations = await async_get_integrations(hass, top_level_components)
    integration_platforms: list[IntegrationPlatform] = hass.data[
        DATA_INTEGRATION_PLATFORMS
    ]
    integration_platform = IntegrationPlatform(
        platform_name, HassJob(process_platform), top_level_components
    )
    integration_platforms.append(integration_platform)
    if futures := [
        future
        for comp in top_level_components
        if (
            platform := _get_platform_from_integration(
                integrations[comp], comp, platform_name
            )
        )
        and (
            future := _async_process_single_integration_platform_component(
                hass, comp, platform, integration_platform
            )
        )
    ]:
        await asyncio.gather(*futures)
