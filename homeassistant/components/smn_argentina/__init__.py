"""The SMN Weather integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ArgentinaSMNDataUpdateCoordinator

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[ArgentinaSMNDataUpdateCoordinator]
) -> bool:
    """Set up SMN from a config entry."""
    # Create coordinator
    coordinator = ArgentinaSMNDataUpdateCoordinator(hass, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    entry.runtime_data = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[ArgentinaSMNDataUpdateCoordinator]
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
