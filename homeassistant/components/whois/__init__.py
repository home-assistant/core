"""The Whois integration."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import WhoisConfigEntry, WhoisCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: WhoisConfigEntry) -> None:
    """Set up from a config entry."""
    coordinator = WhoisCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: WhoisConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
