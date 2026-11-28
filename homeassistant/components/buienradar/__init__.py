"""The buienradar integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import BuienRadarConfigEntry, BuienradarCoordinator

PLATFORMS = [Platform.CAMERA, Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: BuienRadarConfigEntry) -> None:
    """Set up buienradar from a config entry."""
    coordinator = BuienradarCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))


async def async_unload_entry(hass: HomeAssistant, entry: BuienRadarConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, config_entry: BuienRadarConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)
