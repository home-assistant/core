"""Support for Twente Milieu."""

from __future__ import annotations

from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, SENSOR_UNIQUE_ID_MIGRATION
from .coordinator import TwenteMilieuConfigEntry, TwenteMilieuDataUpdateCoordinator

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: TwenteMilieuConfigEntry
) -> bool:
    """Set up Twente Milieu from a config entry."""
    old_prefix = f"{DOMAIN}_{entry.unique_id}_"

    @callback
    def _migrate_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, Any] | None:
        if not entity_entry.unique_id.startswith(old_prefix):
            return None
        old_key = entity_entry.unique_id.removeprefix(old_prefix)
        if (new_key := SENSOR_UNIQUE_ID_MIGRATION.get(old_key)) is None:
            return None
        return {"new_unique_id": f"{entry.unique_id}_{new_key}"}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)

    coordinator = TwenteMilieuDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TwenteMilieuConfigEntry
) -> bool:
    """Unload Twente Milieu config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
