from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["media_player"]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Hegel integration."""
    hass.data.setdefault(DOMAIN, {})

    # Prevent duplicate setup for same entry_id
    if entry.entry_id in hass.data[DOMAIN]:
        _LOGGER.debug("Hegel entry %s already initialized, skipping duplicate setup", entry.entry_id)
        return True

    # Create entry data container
    hass.data[DOMAIN][entry.entry_id] = {}

    # Forward setup to supported platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Hegel entry %s setup completed", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Hegel config entry and stop active client connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data:
            client = entry_data.get("client")
            if client:
                try:
                    _LOGGER.debug("Stopping Hegel client for %s", entry.title)
                    await client.stop()
                except Exception as err:
                    _LOGGER.warning("Error while stopping Hegel client: %s", err)

    return unload_ok
