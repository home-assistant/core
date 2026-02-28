"""The GitHub integration."""

from __future__ import annotations

from types import MappingProxyType

from aiogithubapi import GitHubAPI

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)

from .const import CONF_REPOSITORIES, CONF_REPOSITORY, SUBENTRY_TYPE_REPOSITORY
from .coordinator import GithubConfigEntry, GitHubDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Set up GitHub from a config entry."""
    client = GitHubAPI(
        token=entry.data[CONF_ACCESS_TOKEN],
        session=async_get_clientsession(hass),
        client_name=SERVER_SOFTWARE,
    )

    entry.runtime_data = {}
    for subentry_id, repository_subentry in entry.subentries.items():
        repository = repository_subentry.data[CONF_REPOSITORY]
        coordinator = GitHubDataUpdateCoordinator(
            hass=hass,
            config_entry=entry,
            client=client,
            repository=repository,
        )

        await coordinator.async_config_entry_first_refresh()

        if not entry.pref_disable_polling:
            await coordinator.subscribe()

        entry.runtime_data[subentry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> None:
    """Update entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Unload a config entry."""
    repositories = entry.runtime_data
    for coordinator in repositories.values():
        coordinator.unsubscribe()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.minor_version == 1:
        # In version 1 we added support for multiple repositories, so we need to
        # migrate the old repository to a subentry.
        for repository in entry.options[CONF_REPOSITORIES]:
            subentry = ConfigSubentry(
                data=MappingProxyType({CONF_REPOSITORY: repository}),
                subentry_type=SUBENTRY_TYPE_REPOSITORY,
                title=repository,
                unique_id=repository,
            )

            hass.config_entries.async_add_subentry(entry, subentry)

        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True
