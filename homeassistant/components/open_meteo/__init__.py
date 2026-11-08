"""Support for Open-Meteo."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import OpenMeteoConfigEntry, OpenMeteoDataUpdateCoordinator

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: OpenMeteoConfigEntry) -> None:
    """Set up Open-Meteo from a config entry."""

    coordinator = OpenMeteoDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: OpenMeteoConfigEntry) -> None:
    """Migrate an old config entry."""
    # The zone used to be the unique ID, which config entries don't need
    if entry.minor_version < 2:
        hass.config_entries.async_update_entry(entry, unique_id=None, minor_version=2)


async def async_unload_entry(hass: HomeAssistant, entry: OpenMeteoConfigEntry) -> None:
    """Unload Open-Meteo config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
