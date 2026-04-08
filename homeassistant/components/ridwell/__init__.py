"""The Ridwell integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import LOGGER, SENSOR_TYPE_NEXT_PICKUP
from .coordinator import RidwellConfigEntry, RidwellDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: RidwellConfigEntry) -> bool:
    """Set up Ridwell from a config entry."""
    coordinator = RidwellDataUpdateCoordinator(hass, entry)
    await coordinator.async_initialize()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(options_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def options_update_listener(
    hass: HomeAssistant, entry: RidwellConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RidwellConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    version = entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Update unique ID of existing, single sensor entity to be consistent with
    # common format for platforms going forward:
    if version == 1:
        version = 2
        hass.config_entries.async_update_entry(entry, version=version)

        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any]:
            """Migrate the unique ID to a new format."""
            return {
                "new_unique_id": f"{entity_entry.unique_id}_{SENSOR_TYPE_NEXT_PICKUP}"
            }

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)

    LOGGER.debug("Migration to version %s successful", version)

    return True
