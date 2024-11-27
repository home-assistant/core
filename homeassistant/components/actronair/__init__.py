"""The Actron Air integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api

PLATFORMS: list[Platform] = [Platform.CLIMATE]
type ActronAirAuthConfigEntry = ConfigEntry[api.AsyncConfigEntryAuth]


async def async_setup_entry(
    hass: HomeAssistant, entry: ActronAirAuthConfigEntry
) -> bool:
    """Set up Actron Air from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # If using a requests-based API lib
    # entry.runtime_data = api.ConfigEntryAuth(hass, session)

    # If using an aiohttp-based API lib
    entry.runtime_data = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ActronAirAuthConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
