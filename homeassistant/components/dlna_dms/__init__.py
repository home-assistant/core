"""The DLNA Digital Media Server integration.

A single config entry is used, with SSDP discovery for media servers. Each
server is wrapped in a DmsEntity, and the server's USN is used as the unique_id.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import LOGGER
from .dms import get_domain_data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DLNA DMS device from a config entry."""
    LOGGER.debug("Setting up config entry: %s", entry.unique_id)

    # Forward setup to this domain's data manager
    return await get_domain_data(hass).async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading config entry: %s", entry.unique_id)

    # Forward unload to this domain's data manager
    return await get_domain_data(hass).async_unload_entry(entry)
