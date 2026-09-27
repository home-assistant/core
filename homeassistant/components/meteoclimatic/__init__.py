"""Support for Meteoclimatic weather data."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import MeteoclimaticConfigEntry, MeteoclimaticUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: MeteoclimaticConfigEntry
) -> bool:
    """Set up a Meteoclimatic entry."""
    coordinator = MeteoclimaticUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MeteoclimaticConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
