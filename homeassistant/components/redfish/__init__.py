"""The Redfish integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RedfishConfigEntry, RedfishDataUpdateCoordinator

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: RedfishConfigEntry) -> bool:
    """Set up Redfish from a config entry."""
    coordinator = RedfishDataUpdateCoordinator(hass, entry)
    await coordinator.client.async_login()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RedfishConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.client.async_logout()
    return True
