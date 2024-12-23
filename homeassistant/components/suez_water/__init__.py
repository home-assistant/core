"""The Suez Water integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .config_flow import SuezWaterConfigFlow
from .const import CONF_COUNTER_ID
from .coordinator import SuezWaterConfigEntry, SuezWaterCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SuezWaterConfigEntry) -> bool:
    """Set up Suez Water from a config entry."""

    coordinator = SuezWaterCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SuezWaterConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SuezWaterConfigEntry
) -> bool:
    """Migrate old suez water config entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > SuezWaterConfigFlow.VERSION:
        _LOGGER.error("Suez_water version downgrade not handled")
        return False
    if config_entry.version == 2:
        _LOGGER.debug("Suez_water no minor changes in version 2.X")
        return True

    unique_id = config_entry.unique_id
    if config_entry.version == 1:
        # Going to 2.X
        counter_id = config_entry.data.get(CONF_COUNTER_ID)
        if not counter_id:
            _LOGGER.error(
                "Failed to migrate to suez_water because no counter_id was previously defined"
            )
            return False
        unique_id = str(counter_id)

    hass.config_entries.async_update_entry(
        config_entry,
        unique_id=unique_id,
        minor_version=SuezWaterConfigFlow.MINOR_VERSION,
        version=SuezWaterConfigFlow.VERSION,
    )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
