"""The GeoSphere Austria Warnings integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import GeoSphereConfigEntry, GeoSphereUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GeoSphereConfigEntry) -> bool:
    """Set up GeoSphere Austria Warnings from a config entry."""
    coordinator = GeoSphereUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GeoSphereConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
