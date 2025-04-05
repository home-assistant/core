"""The ntfy integration."""

from __future__ import annotations

from aiontfy import Ntfy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS: list[Platform] = [Platform.NOTIFY]


type NtfyConfigEntry = ConfigEntry[Ntfy]


async def async_setup_entry(hass: HomeAssistant, entry: NtfyConfigEntry) -> bool:
    """Set up ntfy from a config entry."""

    session = async_get_clientsession(hass)
    entry.runtime_data = Ntfy(entry.data[CONF_URL], session)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NtfyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
