"""The GitHub integration."""

from __future__ import annotations

from aiogithubapi import GitHubAPI
import aiohttp

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AsyncConfigEntryAuth
from .const import CONF_REPOSITORIES, DOMAIN, LOGGER
from .coordinator import GithubConfigEntry, GitHubDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GithubConfigEntry) -> bool:
    """Set up GitHub from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = OAuth2Session(hass, entry, implementation)
    async_session = async_get_clientsession(hass)
    config_entry_auth = AsyncConfigEntryAuth(hass, async_session, session)
    try:
        await config_entry_auth.async_get_access_token()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    client = GitHubAPI(
        token=config_entry_auth.session.token["access_token"],
        session=async_session,
        client_name=SERVER_SOFTWARE,
    )

    repositories: list[str] = entry.options[CONF_REPOSITORIES]

    entry.runtime_data = {}
    for repository in repositories:
        coordinator = GitHubDataUpdateCoordinator(
            hass=hass,
            config_entry=entry,
            client=client,
            repository=repository,
        )

        await coordinator.async_config_entry_first_refresh()

        if not entry.pref_disable_polling:
            await coordinator.subscribe()

        entry.runtime_data[repository] = coordinator

    async_cleanup_device_registry(hass=hass, entry=entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def async_cleanup_device_registry(
    hass: HomeAssistant,
    entry: GithubConfigEntry,
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
