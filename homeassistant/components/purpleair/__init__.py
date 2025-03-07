"""The PurpleAir integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .config_schema import ConfigSchema
from .coordinator import PurpleAirConfigEntry, PurpleAirDataUpdateCoordinator

PLATFORMS: Final = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Set up PurpleAir config entry."""
    coordinator = PurpleAirDataUpdateCoordinator(
        hass,
        entry,
    )
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    coordinator.async_delete_orphans_from_device_registry()

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Migrate config entry."""
    return ConfigSchema.async_migrate_entry(hass, entry)


async def async_reload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
