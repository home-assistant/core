"""The Plexilent integration."""

import contextlib

from pyplexilent import Plexilent, PlexilentError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN
from .coordinator import PlexilentConfigEntry, PlexilentCoordinator

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: PlexilentConfigEntry) -> bool:
    """Set up Plexilent from a config entry."""
    client = Plexilent(async_get_clientsession(hass), entry.data[CONF_REFRESH_TOKEN])
    coordinator = PlexilentCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlexilentConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PlexilentConfigEntry) -> None:
    """Revoke the cloud link when the integration is deleted (best effort)."""
    client = Plexilent(async_get_clientsession(hass), entry.data[CONF_REFRESH_TOKEN])
    with contextlib.suppress(PlexilentError):
        await client.unlink()
