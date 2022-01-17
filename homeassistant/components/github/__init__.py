"""The GitHub integration."""
from __future__ import annotations

import asyncio

from aiogithubapi import GitHubAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)

from .const import CONF_REPOSITORIES, DOMAIN
from .coordinator import (
    DataUpdateCoordinators,
    RepositoryCommitDataUpdateCoordinator,
    RepositoryInformationDataUpdateCoordinator,
    RepositoryIssueDataUpdateCoordinator,
    RepositoryReleaseDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GitHub from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = GitHubAPI(
        token=entry.data[CONF_ACCESS_TOKEN],
        session=async_get_clientsession(hass),
        **{"client_name": SERVER_SOFTWARE},
    )

    repositories: list[str] = entry.options[CONF_REPOSITORIES]

    for repository in repositories:
        coordinators: DataUpdateCoordinators = {
            "information": RepositoryInformationDataUpdateCoordinator(
                hass=hass, entry=entry, client=client, repository=repository
            ),
            "release": RepositoryReleaseDataUpdateCoordinator(
                hass=hass, entry=entry, client=client, repository=repository
            ),
            "issue": RepositoryIssueDataUpdateCoordinator(
                hass=hass, entry=entry, client=client, repository=repository
            ),
            "commit": RepositoryCommitDataUpdateCoordinator(
                hass=hass, entry=entry, client=client, repository=repository
            ),
        }

        await asyncio.gather(
            *(
                coordinators["information"].async_config_entry_first_refresh(),
                coordinators["release"].async_config_entry_first_refresh(),
                coordinators["issue"].async_config_entry_first_refresh(),
                coordinators["commit"].async_config_entry_first_refresh(),
            )
        )

        hass.data[DOMAIN][repository] = coordinators

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.pop(DOMAIN)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)
