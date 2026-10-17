"""Home Assistant integration for SOLARMAN devices."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import SolarmanConfigEntry, SolarmanDeviceUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SolarmanConfigEntry) -> None:
    """Set up Solarman from a config entry."""
    coordinator = SolarmanDeviceUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SolarmanConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
