"""The loqed integration."""
from __future__ import annotations

from loqedAPI import loqed

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS: list[str] = [Platform.LOCK]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up loqed from a config entry."""

    websession = async_get_clientsession(hass)
    host = entry.data["host"]
    apiclient = loqed.APIClient(websession, "http://" + host)
    api = loqed.LoqedAPI(apiclient)

    lock = await api.async_get_lock(
        entry.data["api_key"],
        entry.data["bkey"],
        entry.data["key_id"],
        entry.data["host"],
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = lock

    # Registers update listener to update config entry when options are updated.
    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
