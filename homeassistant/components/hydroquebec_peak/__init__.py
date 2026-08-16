"""The Hydro-Québec Peak Events integration."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import HydroQuebecPeakConfigEntry, HydroQuebecPeakCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: HydroQuebecPeakConfigEntry
) -> bool:
    """Set up Hydro-Québec Peak Events from a config entry."""
    coordinator = HydroQuebecPeakCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HydroQuebecPeakConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
