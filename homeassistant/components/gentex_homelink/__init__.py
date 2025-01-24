"""The homelink integration."""

from __future__ import annotations

import logging
from typing import Any

from homelink.provider import Provider

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import DOMAIN
from .coordinator import HomelinkCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

type HomeLinkConfigEntry = ConfigEntry[dict[str, Any]]


async def async_setup_entry(hass: HomeAssistant, entry: HomeLinkConfigEntry) -> bool:
    """Set up homelink from a config entry."""
    logging.debug("Starting config entry setup")
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, api.SRPAuthImplementation(hass, DOMAIN)
    )

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    authenticated_session = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    provider = Provider(authenticated_session)
    coordinator = HomelinkCoordinator(hass, provider, entry)

    entry.runtime_data = {
        "provider": provider,
        "coordinator": coordinator,
        "last_update_id": None,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if update_listener not in entry.update_listeners:
        entry.add_update_listener(update_listener)

    if update_listener not in entry.update_listeners:
        entry.add_update_listener(update_listener)
    await coordinator.async_config_entry_first_refresh()
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomeLinkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
