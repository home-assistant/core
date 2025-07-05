"""The nederlandse_spoorwegen component."""

from __future__ import annotations

import logging
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


# Define runtime data structure for this integration
class NSRuntimeData(TypedDict, total=False):
    """TypedDict for runtime data used by the Nederlandse Spoorwegen integration."""

    # Add actual runtime data fields as needed, e.g.:
    # client: NSAPI


class NSConfigEntry(ConfigEntry[NSRuntimeData]):
    """Config entry for the Nederlandse Spoorwegen integration."""


# Type alias for this integration's config entry
def _cast_entry(entry: ConfigEntry) -> ConfigEntry:
    return entry


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
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
    # Set runtime_data for this entry (replace with actual runtime data as needed)
    entry.runtime_data = NSRuntimeData()
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as err:
        _LOGGER.error("Failed to set up entry: %s", err)
        raise ConfigEntryNotReady from err
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    ns_entry = entry
    await hass.config_entries.async_reload(ns_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading config entry: %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
