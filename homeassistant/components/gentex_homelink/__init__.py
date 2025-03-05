"""The homelink integration."""

from __future__ import annotations

import logging

from homelink.provider import Provider

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import DOMAIN
from .coordinator import HomeLinkCoordinator, HomeLinkData

PLATFORMS: list[Platform] = [Platform.EVENT]

type HomeLinkConfigEntry = ConfigEntry[HomeLinkData]


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
    coordinator = HomeLinkCoordinator(hass, provider, entry)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = HomeLinkData(
        provider=provider, coordinator=coordinator, last_update_id=None
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomeLinkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
