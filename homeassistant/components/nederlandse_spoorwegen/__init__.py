"""The nederlandse_spoorwegen component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""
    _LOGGER.debug("Setting up config entry: %s", entry.entry_id)
    _LOGGER.debug(
        "async_setup_entry called with data: %s, options: %s", entry.data, entry.options
    )
    # Register update listener for options reload
    if "nederlandse_spoorwegen_update_listener" not in hass.data:
        hass.data.setdefault("nederlandse_spoorwegen_update_listener", {})[
            entry.entry_id
        ] = entry.add_update_listener(async_reload_entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    _LOGGER.debug("Reloading config entry: %s due to options update", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading config entry: %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
