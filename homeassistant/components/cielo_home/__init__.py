"""Integration for Cielo Home."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import PLATFORMS
from .coordinator import CieloDataUpdateCoordinator, CieloHomeConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: CieloHomeConfigEntry) -> bool:
    """Set up Cielo Home from a config entry."""
    coordinator = CieloDataUpdateCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CieloHomeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
