"""The GitHub integration."""

from types import MappingProxyType

from aiogithubapi import GitHubAPI

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)

from .const import CONF_REPOSITORIES, CONF_REPOSITORY, DOMAIN, SUBENTRY_TYPE_REPOSITORY
from .coordinator import (
    GithubConfigEntry,
    GitHubDataUpdateCoordinator,
    GitHubRuntimeData,
    GitHubUserDataUpdateCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Set up GitHub from a config entry."""
    client = GitHubAPI(
        token=entry.data[CONF_ACCESS_TOKEN],
        session=async_get_clientsession(hass),
        client_name=SERVER_SOFTWARE,
    )

    user_coordinator = GitHubUserDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
    )
    await user_coordinator.async_config_entry_first_refresh()

    repositories: dict[str, GitHubDataUpdateCoordinator] = {}
    for repository_subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_REPOSITORY):
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

        repositories[repository_subentry.subentry_id] = coordinator

    entry.runtime_data = GitHubRuntimeData(
        user_coordinator=user_coordinator,
        repositories=repositories,
    )

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> None:
    """Update entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Unload a config entry."""
    for coordinator in entry.runtime_data.repositories.values():
        coordinator.unsubscribe()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.minor_version == 1:
        dev_reg = dr.async_get(hass)
        # In minor version 2 we migrated repositories from entry options to
        # subentries, so we need to convert the list from
        # entry.options[CONF_REPOSITORIES] into individual subentries.
        for repository in entry.options[CONF_REPOSITORIES]:
            subentry = ConfigSubentry(
                data=MappingProxyType({CONF_REPOSITORY: repository}),
                subentry_type=SUBENTRY_TYPE_REPOSITORY,
                title=repository,
                unique_id=repository,
            )
            hass.config_entries.async_add_subentry(entry, subentry)
            if device := dev_reg.async_get_device_by_identifier(
                (DOMAIN, repository), entry.entry_id
            ):
                dev_reg.async_update_device(
                    device.id,
                    new_config_entry_id=entry.entry_id,
                    new_config_subentry_id=subentry.subentry_id,
                )
        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True
