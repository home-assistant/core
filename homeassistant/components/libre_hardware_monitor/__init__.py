"""The LibreHardwareMonitor integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import (
    LibreHardwareMonitorConfigEntry,
    LibreHardwareMonitorCoordinator,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: LibreHardwareMonitorConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Migrate from version 1 to 2
        # This migration handles entity unique ID updates

        # Get coordinator to access sensor data
        coordinator = LibreHardwareMonitorCoordinator(hass, config_entry)
        try:
            await coordinator.async_config_entry_first_refresh()
        except (ConnectionError, TimeoutError, OSError) as err:
            _LOGGER.warning("Could not refresh coordinator during migration: %s", err)
            # Continue with migration even if refresh fails

        # Migrate entity unique IDs
        entity_registry = er.async_get(hass)

        if (
            hasattr(coordinator, "data")
            and coordinator.data
            and coordinator.data.sensor_data
        ):
            for sensor_data in coordinator.data.sensor_data.values():
                old_unique_id = f"lhm-{sensor_data.sensor_id}"
                new_unique_id = f"lhm_{config_entry.entry_id}_{sensor_data.sensor_id}"

                _LOGGER.debug(
                    "Checking for entity with old unique_id: %s",
                    old_unique_id,
                )

                # Check if entity exists with old unique ID
                if entity_id := entity_registry.async_get_entity_id(
                    DOMAIN, "sensor", old_unique_id
                ):
                    _LOGGER.debug(
                        "Migrating entity %s from unique_id %s to %s",
                        entity_id,
                        old_unique_id,
                        new_unique_id,
                    )
                    # Remove the old entity - Home Assistant will create a new one with the new unique_id
                    entity_registry.async_remove(entity_id)
                else:
                    _LOGGER.debug(
                        "No entity found with old unique_id: %s",
                        old_unique_id,
                    )

        # Update config entry version
        new_data = {**config_entry.data}
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)

        _LOGGER.info("Migration to version 2 successful")
        return True

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: LibreHardwareMonitorConfigEntry
) -> bool:
    """Set up LibreHardwareMonitor from a config entry."""

    lhm_coordinator = LibreHardwareMonitorCoordinator(hass, config_entry)
    await lhm_coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = lhm_coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: LibreHardwareMonitorConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
