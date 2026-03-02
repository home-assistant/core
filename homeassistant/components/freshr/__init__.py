"""The Fresh-r integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import (
    FreshrConfigEntry,
    FreshrData,
    FreshrDevicesCoordinator,
    FreshrReadingsCoordinator,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: FreshrConfigEntry) -> bool:
    """Set up Fresh-r from a config entry."""
    devices_coordinator = FreshrDevicesCoordinator(hass, entry)
    await devices_coordinator.async_config_entry_first_refresh()

    readings_coordinator = FreshrReadingsCoordinator(hass, entry, devices_coordinator)
    await readings_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = FreshrData(
        devices=devices_coordinator,
        readings=readings_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreshrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
