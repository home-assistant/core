"""The Arve integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import ArveConfigEntry, ArveCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_migrate_entry(hass: HomeAssistant, entry: ArveConfigEntry) -> bool:
    """Migrate entry."""
    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version == 1:
        # 1 -> 1.2: Unique ID from integer to string
        if entry.minor_version == 1:
            minor_version = 2
            hass.config_entries.async_update_entry(
                entry, unique_id=str(entry.unique_id), minor_version=minor_version
            )

    _LOGGER.debug("Migration successful")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ArveConfigEntry) -> bool:
    """Set up Arve from a config entry."""

    coordinator = ArveCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArveConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
