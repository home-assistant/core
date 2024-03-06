"""The Home Assistant Green integration."""
from __future__ import annotations

from homeassistant.components.hassio import get_os_info, is_hassio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant Green config entry."""
    if not is_hassio(hass):
        # Not running under supervisor, Home Assistant may have been migrated
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    if (os_info := get_os_info(hass)) is None:
        # The hassio integration has not yet fetched data from the supervisor
        raise ConfigEntryNotReady

    board: str | None
    if (board := os_info.get("board")) is None or board != "green":
        # Not running on a Home Assistant Green, Home Assistant may have been migrated
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
