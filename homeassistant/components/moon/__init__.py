"""The Moon integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import MoonUpdateCoordinator

type MoonConfigEntry = ConfigEntry[MoonUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MoonConfigEntry) -> bool:
    """Set up from a config entry."""
    coordinator = MoonUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MoonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
