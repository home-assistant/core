"""The Radarr component."""
from __future__ import annotations

from datetime import timedelta

from aiopyarr import RadarrClient, exceptions
from homeassistant.components.radarr.coordinator import RadarrDataUpdateCoordinator

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)

PLATFORMS = ["sensor"]
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Radarr from a config entry."""
    if not entry.options:
        options = {
            CONF_UPCOMING_DAYS: entry.data.get(
                CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
            ),
            CONF_WANTED_MAX_ITEMS: entry.data.get(
                CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
            ),
        }
        hass.config_entries.async_update_entry(entry, options=options)
    api_client = RadarrClient(
        ipaddress=entry.data[CONF_HOST],
        api_token=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
        port=entry.data[CONF_PORT],
    )
    coordinator = RadarrDataUpdateCoordinator(hass, api_client)
    await coordinator.async_config_entry_first_refresh()

    # radarr.basic_auth(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
