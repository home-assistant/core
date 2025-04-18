"""The Adax integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .climate import AdaxDataHandler
from .const import PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Adax from a config entry."""
    adax_data_handler = AdaxDataHandler(entry, hass)
    await adax_data_handler.async_update()
    hass.data[entry.entry_id] = adax_data_handler

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # convert title and unique_id to string
    if config_entry.version == 1:
        if isinstance(config_entry.unique_id, int):
            hass.config_entries.async_update_entry(  # type: ignore[unreachable]
                config_entry,
                unique_id=str(config_entry.unique_id),
                title=str(config_entry.title),
            )

    return True
