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
    async_register_preload_platform,
    bind_hass,
)
from homeassistant.setup import ATTR_COMPONENT, EventComponentLoaded
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.logging import catch_log_exception

_LOGGER = logging.getLogger(__name__)
DATA_INTEGRATION_PLATFORMS: HassKey[list[IntegrationPlatform]] = HassKey(
    "integration_platforms"
)


@dataclass(slots=True, frozen=True)
class IntegrationPlatform:
    """An integration platform."""

    platform_name: str
    process_job: HassJob[[HomeAssistant, str, Any], Awaitable[None] | None]
    seen_components: set[str]


@callback
def _async_integration_platform_component_loaded(
    hass: HomeAssistant,
    integration_platforms: list[IntegrationPlatform],
    event: Event[EventComponentLoaded],
) -> None:
    """Process integration platforms for a component."""
    if "." in (component_name := event.data[ATTR_COMPONENT]):
        return

    integration = async_get_loaded_integration(hass, component_name)
    # First filter out platforms that the integration already processed.
    integration_platforms_by_name: dict[str, IntegrationPlatform] = {}
    for integration_platform in integration_platforms:
        if component_name in integration_platform.seen_components:
            continue
        integration_platform.seen_components.add(component_name)
        integration_platforms_by_name[integration_platform.platform_name] = (
            integration_platform
        )

    if not integration_platforms_by_name:
        return

    # Next, check which platforms exist for this integration.
    platforms_that_exist = integration.platforms_exists(integration_platforms_by_name)
    if not platforms_that_exist:
        return

    # If everything is already loaded, we can avoid creating a task.
    can_use_cache = True
    platforms: dict[str, ModuleType] = {}
    for platform_name in platforms_that_exist:
        if platform := integration.get_platform_cached(platform_name):
            platforms[platform_name] = platform
        else:
            can_use_cache = False
            break

    if can_use_cache:
        _process_integration_platforms(
            hass,
            integration,
            platforms,
            integration_platforms_by_name,
        )
        return

    # At least one of the platforms is not loaded, we need to load them
    # so we have to fall back to creating a task.
    hass.async_create_task_internal(
        _async_process_integration_platforms_for_component(
            hass, integration, platforms_that_exist, integration_platforms_by_name
        ),
        eager_start=True,
    )


async def _async_process_integration_platforms_for_component(
    hass: HomeAssistant,
    integration: Integration,
    platforms_that_exist: list[str],
    integration_platforms_by_name: dict[str, IntegrationPlatform],
) -> None:
    """Process integration platforms for a component."""
    # Now we know which platforms to load, let's load them.
    try:
        platforms = await integration.async_get_platforms(platforms_that_exist)
    except ImportError:
        _LOGGER.debug(
            "Unexpected error importing integration platforms for %s",
            integration.domain,
        )
        return

    if futures := _process_integration_platforms(
        hass,
        integration,
        platforms,
        integration_platforms_by_name,
    ):
        await asyncio.gather(*futures)


@callback
def _process_integration_platforms(
    hass: HomeAssistant,
    integration: Integration,
    platforms: dict[str, ModuleType],
    integration_platforms_by_name: dict[str, IntegrationPlatform],
) -> list[asyncio.Future[Awaitable[None] | None]]:
    """Process integration platforms for a component.

    Only the platforms that are passed in will be processed.
    """
    return [
        future
        for platform_name, platform in platforms.items()
        if (integration_platform := integration_platforms_by_name[platform_name])
        and (
            future := hass.async_run_hass_job(
                integration_platform.process_job,
                hass,
                integration.domain,
                platform,
            )
        )
    ]


def _format_err(name: str, platform_name: str, *args: Any) -> str:
    """Format error message."""
    return f"Exception in {name} when processing platform '{platform_name}': {args}"


@bind_hass
async def async_process_integration_platforms(
    hass: HomeAssistant,
    platform_name: str,
    # Any = platform.
    process_platform: Callable[[HomeAssistant, str, Any], Awaitable[None] | None],
    wait_for_platforms: bool = False,
) -> None:
    """Process a specific platform for all current and future loaded integrations."""
    if DATA_INTEGRATION_PLATFORMS not in hass.data:
        integration_platforms = hass.data[DATA_INTEGRATION_PLATFORMS] = []
        hass.bus.async_listen(
            EVENT_COMPONENT_LOADED,
            partial(
                _async_integration_platform_component_loaded,
                hass,
                integration_platforms,
            ),
        )
    else:
        integration_platforms = hass.data[DATA_INTEGRATION_PLATFORMS]

    async_register_preload_platform(hass, platform_name)
    top_level_components = hass.config.top_level_components.copy()
    process_job = HassJob(
        catch_log_exception(
            process_platform,
            partial(_format_err, str(process_platform), platform_name),
        ),
        f"process_platform {platform_name}",
    )
    integration_platform = IntegrationPlatform(
        platform_name, process_job, top_level_components
    )
    # Tell the loader that it should try to pre-load the integration
    # for any future components that are loaded so we can reduce the
    # amount of import executor usage.
    async_register_preload_platform(hass, platform_name)
    integration_platforms.append(integration_platform)
    if not top_level_components:
        return

    # We create a task here for two reasons:
    #
    # 1. We want the integration that provides the integration platform to
    #    not be delayed by waiting on each individual platform to be processed
    #    since the import or the integration platforms themselves may have to
    #    schedule I/O or executor jobs.
    #
    # 2. We want the behavior to be the same as if the integration that has
    #    the integration platform is loaded after the platform is processed.
    #
    # We use hass.async_create_task instead of asyncio.create_task because
    # we want to make sure that startup waits for the task to complete.
    #
    future = hass.async_create_task_internal(
        _async_process_integration_platforms(
            hass, platform_name, top_level_components.copy(), process_job
        ),
        eager_start=True,
    )
    if wait_for_platforms:
        await future


async def _async_process_integration_platforms(
    hass: HomeAssistant,
    platform_name: str,
    top_level_components: set[str],
    process_job: HassJob,
) -> None:
    """Process integration platforms for a component."""
    integrations = await async_get_integrations(hass, top_level_components)
    loaded_integrations: list[Integration] = [
        integration
        for integration in integrations.values()
        if not isinstance(integration, Exception)
    ]
    # Finally, fetch the platforms for each integration and process them.
    # This uses the import executor in a loop. If there are a lot
    # of integration with the integration platform to process,
    # this could be a bottleneck.
    futures: list[asyncio.Future[None]] = []
    for integration in loaded_integrations:
        if not integration.platforms_exists((platform_name,)):
            continue
        try:
            platform = await integration.async_get_platform(platform_name)
        except ImportError:
            _LOGGER.debug(
                "Unexpected error importing %s for %s",
                platform_name,
                integration.domain,
            )
            continue

        if future := hass.async_run_hass_job(
            process_job, hass, integration.domain, platform
        ):
            futures.append(future)

    if futures:
        await asyncio.gather(*futures)
