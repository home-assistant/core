"""The Moulinex integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MoulinexConfigEntry, MoulinexDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MoulinexConfigEntry) -> None:
    """Set up Moulinex from a config entry."""
    coordinator = MoulinexDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MoulinexConfigEntry) -> None:
    """Unload a Moulinex config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
