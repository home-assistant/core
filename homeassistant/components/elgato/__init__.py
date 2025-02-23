"""Support for Elgato Lights."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ElgatoConfigEntry, ElgatoDataUpdateCoordinator

PLATFORMS = [Platform.BUTTON, Platform.LIGHT, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ElgatoConfigEntry) -> bool:
    """Set up Elgato Light from a config entry."""
    coordinator = ElgatoDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElgatoConfigEntry) -> bool:
    """Unload Elgato Light config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
