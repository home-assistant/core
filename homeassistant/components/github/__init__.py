"""The GitHub integration."""

from __future__ import annotations

from aiogithubapi import GitHubAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)

from .const import CONF_REPOSITORIES, DOMAIN, LOGGER
from .coordinator import GitHubDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


type GithubConfigEntry = ConfigEntry[dict[str, GitHubDataUpdateCoordinator]]


async def async_setup_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Set up GitHub from a config entry."""
    client = GitHubAPI(
        token=entry.data[CONF_ACCESS_TOKEN],
        session=async_get_clientsession(hass),
        client_name=SERVER_SOFTWARE,
    )

    repositories: list[str] = entry.options[CONF_REPOSITORIES]

    entry.runtime_data = {}
    for repository in repositories:
        coordinator = GitHubDataUpdateCoordinator(
            hass=hass,
            client=client,
            repository=repository,
        )

        await coordinator.async_config_entry_first_refresh()

        if not entry.pref_disable_polling:
            await coordinator.subscribe()

        entry.runtime_data[repository] = coordinator

    async_cleanup_device_registry(hass=hass, entry=entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


@callback
def async_cleanup_device_registry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove entries form device registry if we no longer track the repository."""
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=entry.entry_id,
    )
    for device in devices:
        for item in device.identifiers:
            if item[0] == DOMAIN and item[1] not in entry.options[CONF_REPOSITORIES]:
                LOGGER.debug(
                    (
                        "Unlinking device %s for untracked repository %s from config"
                        " entry %s"
                    ),
                    device.id,
                    item[1],
                    entry.entry_id,
                )
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=entry.entry_id
                )
                break


async def async_unload_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Unload a config entry."""
    repositories = entry.runtime_data
    for coordinator in repositories.values():
        coordinator.unsubscribe()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)
