"""Implements the enasolar component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the config entry."""
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)
