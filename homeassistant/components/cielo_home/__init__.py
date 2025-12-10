"""init file for Cielo integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import CieloDataUpdateCoordinator

CONFIG_ENTRY_VERSION = 1

type CieloHomeConfigEntry = ConfigEntry[CieloDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CieloHomeConfigEntry) -> bool:
    """Set up Cielo Home from a config entry."""
    coordinator = CieloDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CieloHomeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry data to the new version."""
    target_version = 2
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data["api_key"], version=target_version
        )
        entry.version = target_version
    return True
