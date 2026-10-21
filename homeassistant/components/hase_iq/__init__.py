"""The Hase iQ integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import HaseIQConfigEntry, HaseIQCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HaseIQConfigEntry) -> None:
    """Set up Hase iQ from a config entry."""
    coordinator = HaseIQCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HaseIQConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
