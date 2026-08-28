"""The Discogs integration."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import DiscogsConfigEntry, DiscogsDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: DiscogsConfigEntry) -> bool:
    """Set up Discogs from a config entry."""
    coordinator = DiscogsDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DiscogsConfigEntry) -> bool:
    """Unload Discogs config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
