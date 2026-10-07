"""Services for the command_line integration."""

import asyncio
from collections.abc import Coroutine
from typing import Any

from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import discovery
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, PLATFORM_MAPPING
from .utils import async_prune_shell_template_issues, shell_template_issue_ids


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


async def _async_reload_config(call: ServiceCall) -> None:
    """Reload Command Line."""
    hass = call.hass
    reload_config = await async_integration_yaml_config(hass, DOMAIN)
    reset_platforms = async_get_platforms(hass, DOMAIN)
    for reset_platform in reset_platforms:
        LOGGER.debug("Reload resetting platform: %s", reset_platform.domain)
        await reset_platform.async_reset()
    # Prune template deprecation issues for entities that no longer exist,
    # keeping issues for still-configured entities so an ignored issue is not
    # reset by a delete-and-recreate. Each entity refreshes or clears its own
    # issue on its next update after reload.
    valid_issue_ids = shell_template_issue_ids(
        reload_config.get(DOMAIN, []) if reload_config else []
    )
    async_prune_shell_template_issues(hass, valid_issue_ids)
    if not reload_config:
        return
    await async_load_platforms(hass, reload_config.get(DOMAIN, []), reload_config)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the command_line services."""
    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _async_reload_config)
