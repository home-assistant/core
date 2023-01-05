"""Class to reload platforms."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant import config as conf_util
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from . import config_per_platform
from .entity import Entity
from .entity_component import EntityComponent
from .entity_platform import EntityPlatform, async_get_platforms
from .service import async_register_admin_service
from .typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORM_RESET_LOCK = "lock_async_reset_platform_{}"


async def async_reload_integration_platforms(
    hass: HomeAssistant, integration_name: str, integration_platforms: Iterable[str]
) -> None:
    """Reload an integration's platforms.

    The platform must support being re-setup.

    This functionality is only intended to be used for integrations that process
    Home Assistant data and make this available to other integrations.

    Examples are template, stats, derivative, utility meter.
    """
    try:
        unprocessed_conf = await conf_util.async_hass_config_yaml(hass)
    except HomeAssistantError as err:
        _LOGGER.error(err)
        return

    tasks = [
        _resetup_platform(
            hass, integration_name, integration_platform, unprocessed_conf
        )
        for integration_platform in integration_platforms
    ]

    await asyncio.gather(*tasks)


async def _resetup_platform(
    hass: HomeAssistant,
    integration_name: str,
    integration_platform: str,
    unprocessed_conf: ConfigType,
) -> None:
    """Resetup a platform."""
    integration = await async_get_integration(hass, integration_platform)

    conf = await conf_util.async_process_component_config(
        hass, unprocessed_conf, integration
    )

    if not conf:
        return

    root_config: dict[str, list[ConfigType]] = {integration_platform: []}
    # Extract only the config for template, ignore the rest.
    for p_type, p_config in config_per_platform(conf, integration_platform):
        if p_type != integration_name:
            continue

        root_config[integration_platform].append(p_config)

    component = integration.get_component()

    if hasattr(component, "async_reset_platform"):
        # If the integration has its own way to reset
        # use this method.
        async with hass.data.setdefault(
            PLATFORM_RESET_LOCK.format(integration_platform), asyncio.Lock()
        ):
            await component.async_reset_platform(hass, integration_name)
            await component.async_setup(hass, root_config)
        return

    # If it's an entity platform, we use the entity_platform
    # async_reset method
    platform = async_get_platform_without_config_entry(
        hass, integration_name, integration_platform
    )
    if platform:
        await _async_reconfig_platform(platform, root_config[integration_platform])
        return

    if not root_config[integration_platform]:
        # No config for this platform
        # and it's not loaded. Nothing to do.
        return

    await _async_setup_platform(
        hass, integration_name, integration_platform, root_config[integration_platform]
    )


async def _async_setup_platform(
    hass: HomeAssistant,
    integration_name: str,
    integration_platform: str,
    platform_configs: list[dict[str, Any]],
) -> None:
    """Platform for the first time when new configuration is added."""
    if integration_platform not in hass.data:
        await async_setup_component(
            hass, integration_platform, {integration_platform: platform_configs}
        )
        return

    entity_component: EntityComponent[Entity] = hass.data[integration_platform]
    tasks = [
        entity_component.async_setup_platform(integration_name, p_config)
        for p_config in platform_configs
    ]
    await asyncio.gather(*tasks)


async def _async_reconfig_platform(
    platform: EntityPlatform, platform_configs: list[dict[str, Any]]
) -> None:
    """Reconfigure an already loaded platform."""
    await platform.async_reset()
    tasks = [platform.async_setup(p_config) for p_config in platform_configs]
    await asyncio.gather(*tasks)


async def async_integration_yaml_config(
    hass: HomeAssistant, integration_name: str
) -> ConfigType | None:
    """Fetch the latest yaml configuration for an integration."""
    integration = await async_get_integration(hass, integration_name)

    return await conf_util.async_process_component_config(
        hass, await conf_util.async_hass_config_yaml(hass), integration
    )


@callback
def async_get_platform_without_config_entry(
    hass: HomeAssistant, integration_name: str, integration_platform_name: str
) -> EntityPlatform | None:
    """Find an existing platform that is not a config entry."""
    for integration_platform in async_get_platforms(hass, integration_name):
        if integration_platform.config_entry is not None:
            continue
        if integration_platform.domain == integration_platform_name:
            platform: EntityPlatform = integration_platform
            return platform

    return None


async def async_setup_reload_service(
    hass: HomeAssistant, domain: str, platforms: Iterable[str]
) -> None:
    """Create the reload service for the domain."""
    if hass.services.has_service(domain, SERVICE_RELOAD):
        return

    async def _reload_config(call: ServiceCall) -> None:
        """Reload the platforms."""
        await async_reload_integration_platforms(hass, domain, platforms)
        hass.bus.async_fire(f"event_{domain}_reloaded", context=call.context)

    async_register_admin_service(hass, domain, SERVICE_RELOAD, _reload_config)


def setup_reload_service(
    hass: HomeAssistant, domain: str, platforms: Iterable[str]
) -> None:
    """Sync version of async_setup_reload_service."""
    asyncio.run_coroutine_threadsafe(
        async_setup_reload_service(hass, domain, platforms),
        hass.loop,
    ).result()
