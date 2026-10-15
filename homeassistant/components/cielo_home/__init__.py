"""Integration for Cielo Home."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import CieloDataUpdateCoordinator, CieloHomeConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: CieloHomeConfigEntry) -> None:
    """Set up Cielo Home from a config entry."""
    coordinator = CieloDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: CieloHomeConfigEntry) -> None:
    """Unload a config entry."""
    coordinator = entry.runtime_data
    await coordinator.async_shutdown()
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
