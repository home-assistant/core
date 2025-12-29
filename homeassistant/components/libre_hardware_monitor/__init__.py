"""The LibreHardwareMonitor integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    """Migrate non-unique entity and device ids."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Migrate entity identifiers
        entity_registry = er.async_get(hass)
        registry_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for reg_entry in registry_entries:
            new_unique_id = f"{config_entry.entry_id}_{reg_entry.unique_id[4:]}"
            _LOGGER.debug(
                "Migrating entity %s unique id from %s to %s",
                reg_entry.entity_id,
                reg_entry.unique_id,
                new_unique_id,
            )
            entity_registry.async_update_entity(
                reg_entry.entity_id, new_unique_id=new_unique_id
            )

        # Migrate device identifiers
        device_registry = dr.async_get(hass)
        device_entries = dr.async_entries_for_config_entry(
            registry=device_registry, config_entry_id=config_entry.entry_id
        )
        for device in device_entries:
            old_device_id = next(iter(device.identifiers))[1]
            new_device_id = f"{config_entry.entry_id}_{old_device_id}"
            _LOGGER.debug(
                "Migrating device %s unique id from %s to %s",
                device.name,
                old_device_id,
                new_device_id,
            )
            device_registry.async_update_device(
                device_id=device.id,
                new_identifiers={(DOMAIN, new_device_id)},
            )

        hass.config_entries.async_update_entry(
            config_entry, data=config_entry.data, version=2
        )

        _LOGGER.debug("Migration to version 2 successful")
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
