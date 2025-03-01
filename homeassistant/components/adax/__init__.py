"""The Adax integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONNECTION_TYPE, LOCAL
from .coordinator import AdaxCloudCoordinator, AdaxLocalCoordinator

PLATFORMS = [Platform.CLIMATE]

type AdaxConfigEntry = ConfigEntry[AdaxCloudCoordinator | AdaxLocalCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AdaxConfigEntry) -> bool:
    """Set up Adax from a config entry."""
    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        coordinator = AdaxLocalCoordinator(hass, entry)
    else:
        coordinator = AdaxCloudCoordinator(hass, entry)

    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # convert title and unique_id to string
    if config_entry.version == 1:
        if isinstance(config_entry.unique_id, int):
            hass.config_entries.async_update_entry(  # type: ignore[unreachable]
                config_entry,
                unique_id=str(config_entry.unique_id),
                title=str(config_entry.title),
            )

    return True
