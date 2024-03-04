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
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.loader import (
    Integration,
    async_get_integrations,
    async_get_loaded_integration,
    async_register_preload_platform,
    bind_hass,
)
from homeassistant.setup import ATTR_COMPONENT, EventComponentLoaded
from homeassistant.util.logging import catch_log_exception

from .typing import EventType

_LOGGER = logging.getLogger(__name__)
DATA_INTEGRATION_PLATFORMS = "integration_platforms"


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
    event: EventType[EventComponentLoaded],
) -> None:
    """Process integration platforms for a component."""
    if "." in (component_name := event.data[ATTR_COMPONENT]):
        return

    integration = async_get_loaded_integration(hass, component_name)
    # First filter out platforms that the integration already
    # known to be missing or already processed.
    to_process: list[IntegrationPlatform] = []
    for integration_platform in integration_platforms:
        if component_name in integration_platform.seen_components:
            continue
        integration_platform.seen_components.add(component_name)
        if not integration.platform_missing(integration_platform.platform_name):
            to_process.append(integration_platform)

    if not to_process:
        return

    # If everything is already loaded, we can avoid creating a task.
    can_use_cache = True
    integration_platforms_to_load: dict[str, IntegrationPlatform] = {}
    platforms: dict[str, ModuleType] = {}
    for integration_platform in to_process:
        platform_name = integration_platform.platform_name
        if platform := integration.get_platform_cached(platform_name):
            integration_platforms_to_load[platform_name] = integration_platform
            platforms[platform_name] = platform
        else:
            can_use_cache = False
            break

    if can_use_cache:
        _process_integration_platforms(
            hass, integration, integration_platforms_to_load, platforms
        )
        return

    # At least one of the platforms is not loaded, we need to load them
    # so we have to fall back to creating a task.
    hass.async_create_task(
        _async_process_integration_platforms_for_component(
            hass, integration, to_process
        ),
        eager_start=True,
    )


async def _async_process_integration_platforms_for_component(
    hass: HomeAssistant,
    integration: Integration,
    integration_platforms: list[IntegrationPlatform],
) -> None:
    """Process integration platforms for a component."""
    # Create an executor job to filter out platforms that we don't know
    # if they are missing or not.
    #
    # We use the normal executor and not the import executor as we
    # we are not importing anything and only going to stat()
    # files.
    integration_platforms_by_name = {
        integration_platform.platform_name: integration_platform
        for integration_platform in integration_platforms
    }
    platforms_that_exist = await hass.async_add_executor_job(
        integration.platforms_exists, integration_platforms_by_name
    )

    if not platforms_that_exist:
        return

    # Now we know which platforms to load, let's load them.
    try:
        platforms = await integration.async_get_platforms(platforms_that_exist)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception(
            "Unexpected error importing integration platforms for %s",
            integration.domain,
        )
        return

    if futures := _process_integration_platforms(
        hass, integration, integration_platforms_by_name, platforms
    ):
        await asyncio.gather(*futures)


@callback
def _process_integration_platforms(
    hass: HomeAssistant,
    integration: Integration,
    integration_platforms_to_load: dict[str, IntegrationPlatform],
    platforms: dict[str, ModuleType],
) -> list[asyncio.Future[Awaitable[None] | None]]:
    """Process integration platforms for a component."""
    return [
        future
        for platform_name, platform in platforms.items()
        if (integration_platform := integration_platforms_to_load[platform_name])
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


def _get_integrations_with_platform(
    platform_name: str,
    integrations: list[Integration],
) -> list[Integration]:
    """Filter out integrations that have a platform.

    This function is executed in an executor.
    """
    return [
        integration
        for integration in integrations
        if integration.platforms_exists((platform_name,))
    ]


@bind_hass
async def async_process_integration_platforms(
    hass: HomeAssistant,
    platform_name: str,
    # Any = platform.
    process_platform: Callable[[HomeAssistant, str, Any], Awaitable[None] | None],
) -> None:
    """Process a specific platform for all current and future loaded integrations."""
    if DATA_INTEGRATION_PLATFORMS not in hass.data:
        integration_platforms: list[IntegrationPlatform] = []
        hass.data[DATA_INTEGRATION_PLATFORMS] = integration_platforms
        hass.bus.async_listen(
            EVENT_COMPONENT_LOADED,
            partial(
                _async_integration_platform_component_loaded,
                hass,
                integration_platforms,
            ),
            run_immediately=True,
        )
    else:
        integration_platforms = hass.data[DATA_INTEGRATION_PLATFORMS]

    top_level_components = {comp for comp in hass.config.components if "." not in comp}
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

    integrations = await async_get_integrations(hass, top_level_components)
    loaded_integrations: list[Integration] = []
    for domain, integration in integrations.items():
        if isinstance(integration, Exception):
            _LOGGER.exception(
                "Error importing integration %s for %s",
                domain,
                platform_name,
                exc_info=integration,
            )
            continue
        loaded_integrations.append(integration)

    if not loaded_integrations:
        return

    # If the platform is known to be missing exclude it right
    # away from the list of integrations to process.
    integrations_not_missing_platform = [
        integration
        for integration in loaded_integrations
        if not integration.platform_missing(platform_name)
    ]
    if not integrations_not_missing_platform:
        return

    # Now we create an executor job to filter out integrations that we
    # don't know if they have the platform or not already.
    #
    # We use the normal executor and not the import executor as we
    # we are not importing anything and only going to stat()
    # files.
    integrations_with_platforms = await hass.async_add_executor_job(
        _get_integrations_with_platform,
        platform_name,
        integrations_not_missing_platform,
    )
    futures: list[asyncio.Future[None]] = []

    # Finally, fetch the platforms for each integration and process them.
    # This uses the import executor in a loop. If there are a lot
    # of integration with the integration platform to process,
    # this could be a bottleneck.
    for integration_with_platform in integrations_with_platforms:
        try:
            platform = await integration_with_platform.async_get_platform(platform_name)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unexpected error importing %s for %s",
                platform_name,
                integration_with_platform.domain,
            )
            continue

        if future := hass.async_run_hass_job(
            process_job, hass, integration_with_platform.domain, platform
        ):
            futures.append(future)

    if futures:
        await asyncio.gather(*futures)
