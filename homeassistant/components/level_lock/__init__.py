"""The Level Lock integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import (
    CONF_OAUTH2_BASE_URL,
    CONF_PARTNER_BASE_URL,
    DEFAULT_OAUTH2_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DOMAIN,
)
from .coordinator import LevelApiClient, LevelLocksCoordinator

# For your initial PR, limit it to 1 platform.
_PLATFORMS: list[Platform] = [Platform.LOCK]

# TODO Create ConfigEntry type alias with ConfigEntryAuth or AsyncConfigEntryAuth object
# TODO Rename type alias and update all entry annotations
type New_NameConfigEntry = ConfigEntry[api.AsyncConfigEntryAuth]


async def async_setup_entry(hass: HomeAssistant, entry: New_NameConfigEntry) -> bool:
    """Set up Level Lock from a config entry."""
    # Store selected base URLs for runtime access by application_credentials
    if entry.options:
        hass.data.setdefault(DOMAIN, {})[CONF_OAUTH2_BASE_URL] = entry.options.get(
            CONF_OAUTH2_BASE_URL
        )
        hass.data[DOMAIN][CONF_PARTNER_BASE_URL] = entry.options.get(
            CONF_PARTNER_BASE_URL
        )
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Use an aiohttp-based auth helper for async calls
    auth = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )
    entry.runtime_data = auth

    # Build resource API client and coordinator here (bind config_entry to coordinator)
    # Use the partner base URL for device APIs
    base_url = (hass.data.get(DOMAIN) or {}).get(
        CONF_PARTNER_BASE_URL
    ) or DEFAULT_PARTNER_BASE_URL
    client = LevelApiClient(hass, auth, base_url)
    coordinator = LevelLocksCoordinator(hass, client, config_entry=entry)
    # First refresh: if it fails due to network/auth, raise ConfigEntryNotReady here
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for platforms
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


# TODO Update entry annotation
async def async_unload_entry(hass: HomeAssistant, entry: New_NameConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unloaded and DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
