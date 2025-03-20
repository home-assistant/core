"""The Derivative integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SOURCE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import (
    async_remove_stale_devices_links_keep_entity_device,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Derivative from a config entry."""

    async_remove_stale_devices_links_keep_entity_device(
        hass, entry.entry_id, entry.options[CONF_SOURCE]
    )

    await hass.config_entries.async_forward_entry_setups(entry, (Platform.SENSOR,))
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, (Platform.SENSOR,))
