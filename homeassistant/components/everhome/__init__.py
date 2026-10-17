"""The EcoTracker integration."""

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .coordinator import EcoTrackerConfigEntry, EcoTrackerDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EcoTrackerConfigEntry) -> bool:
    """Set up EcoTracker from a config entry."""

    coordinator = EcoTrackerDataUpdateCoordinator(
        hass,
        host=entry.data[CONF_HOST],
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EcoTrackerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
