"""Support for Enigma2 devices."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import Enigma2ConfigEntry, Enigma2UpdateCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: Enigma2ConfigEntry) -> None:
    """Set up Enigma2 from a config entry."""

    coordinator = Enigma2UpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: Enigma2ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
