"""The Linksys Smart Wi-Fi integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import LinksysConfigEntry, LinksysDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: LinksysConfigEntry) -> bool:
    """Set up Linksys from a config entry."""
    coordinator = LinksysDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinksysConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
