"""The free_mobile component."""

from __future__ import annotations

from freesms import FreeClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.NOTIFY]


type FreeMobileConfigEntry = ConfigEntry[FreeClient]


async def async_setup_entry(hass: HomeAssistant, entry: FreeMobileConfigEntry) -> bool:
    """Set up Free Mobile from a config entry."""
    client = FreeClient(entry.data[CONF_USERNAME], entry.data[CONF_ACCESS_TOKEN])

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreeMobileConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
