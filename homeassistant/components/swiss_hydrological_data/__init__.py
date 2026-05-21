"""The Swiss Hydrological Data integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SwissHydrologicalDataCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type SwissHydroConfigEntry = ConfigEntry[SwissHydrologicalDataCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SwissHydroConfigEntry) -> bool:
    """Set up Swiss Hydrological Data from a config entry."""
    coordinator = SwissHydrologicalDataCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SwissHydroConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
