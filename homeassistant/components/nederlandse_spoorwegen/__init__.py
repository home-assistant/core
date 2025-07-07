"""The nederlandse_spoorwegen component."""

from __future__ import annotations

import logging
from typing import TypedDict

from ns_api import NSAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


# Define runtime data structure for this integration
class NSRuntimeData(TypedDict, total=False):
    """TypedDict for runtime data used by the Nederlandse Spoorwegen integration."""

    client: NSAPI


class NSConfigEntry(ConfigEntry[NSRuntimeData]):
    """Config entry for the Nederlandse Spoorwegen integration."""


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Set runtime_data for this entry (store the NSAPI client)
    api_key = entry.data.get(CONF_API_KEY)
    client = NSAPI(api_key)
    # Test connection before setting up platforms
    try:
        await hass.async_add_executor_job(client.get_stations)
    except Exception as err:
        _LOGGER.error("Failed to connect to NS API: %s", err)
        raise ConfigEntryNotReady from err
    entry.runtime_data = NSRuntimeData(client=client)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    ns_entry = entry
    await hass.config_entries.async_reload(ns_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
