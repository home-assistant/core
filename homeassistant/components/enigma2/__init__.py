"""Support for Enigma2 devices."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import Enigma2UpdateCoordinator

type Enigma2ConfigEntry = ConfigEntry[Enigma2UpdateCoordinator]

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: Enigma2ConfigEntry) -> bool:
    """Set up Enigma2 from a config entry."""

    coordinator = Enigma2UpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
