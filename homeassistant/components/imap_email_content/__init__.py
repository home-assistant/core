"""The imap_email_content component."""


from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]


async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle signals of config entry being updated.

    Causes for this is config entry options changing.
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry_data: dict[str, Any] = hass.data.setdefault(DOMAIN, {})
    entry_data[entry.entry_id] = entry.add_update_listener(_async_config_entry_updated)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    entry_data: dict[str, Any] = hass.data[DOMAIN]
    entry_data[entry.entry_id]()
    return unload_ok
