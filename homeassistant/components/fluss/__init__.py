"""The Fluss+ integration."""

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .coordinator import FlussConfigEntry, FlussDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.COVER]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlussConfigEntry,
) -> None:
    """Set up Fluss+ from a config entry."""
    coordinator = FlussDataUpdateCoordinator(hass, entry, entry.data[CONF_API_KEY])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: FlussConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
