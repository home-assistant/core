"""The Fluss+ integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .coordinator import FlussConfigEntry, FlussDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
) -> bool:
    """Set up Fluss+ from a config entry."""
    coordinator = FlussDataUpdateCoordinator(hass, entry, entry.data[CONF_API_KEY])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlussConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: FlussConfigEntry
) -> None:
    """Handle options update — reload the integration to pick up icon changes."""
    await hass.config_entries.async_reload(entry.entry_id)
