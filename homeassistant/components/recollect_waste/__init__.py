"""The ReCollect Waste integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, DOMAIN, LOGGER
from .coordinator import ReCollectWasteDataUpdateCoordinator

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ReCollect Waste as config entry."""
    coordinator = ReCollectWasteDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an ReCollect Waste config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


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
                "new_unique_id": (
                    f"{entry.data[CONF_PLACE_ID]}_"
                    f"{entry.data[CONF_SERVICE_ID]}_"
                    "current_pickup"
                )
            }

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)

    LOGGER.debug("Migration to version %s successful", version)

    return True
