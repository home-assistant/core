"""Solar-Log integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .coordinator import SolarLogCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
type SolarlogConfigEntry = ConfigEntry[SolarLogCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SolarlogConfigEntry) -> bool:
    """Set up a config entry for solarlog."""
    entry.async_on_unload(entry.add_update_listener(update_listener))
    coordinator = SolarLogCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarlogConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SolarlogConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        if config_entry.minor_version < 2:
            # migrate old entity unique id
            entity_reg = er.async_get(hass)
            entities: list[er.RegistryEntry] = er.async_entries_for_config_entry(
                entity_reg, config_entry.entry_id
            )

            for entity in entities:
                if "time" in entity.unique_id:
                    new_uid = entity.unique_id.replace("time", "last_updated")
                    _LOGGER.debug(
                        "migrate unique id '%s' to '%s'", entity.unique_id, new_uid
                    )
                    entity_reg.async_update_entity(
                        entity.entity_id, new_unique_id=new_uid
                    )

            # migrate config_entry
            new = {**config_entry.data}
            new["extended_data"] = False

            hass.config_entries.async_update_entry(
                config_entry, data=new, minor_version=2, version=1
            )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def update_listener(hass: HomeAssistant, entry: SolarlogConfigEntry) -> None:
    """Handle options update."""

    # remove devices that have been checked-off
    coordinator: SolarLogCoordinator = entry.runtime_data

    device_reg = dr.async_get(hass)

    device_list = dr.async_entries_for_config_entry(device_reg, entry.entry_id)

    for device_entry in device_list:
        if device_entry.model == "Controller":
            # Controller device cannot be removed
            continue

        for key in coordinator.solarlog.device_enabled():
            if device_entry.name == coordinator.solarlog.device_name(key):
                if not coordinator.solarlog.device_enabled(key):
                    _LOGGER.debug(
                        "Device %s removed",
                        device_entry.name,
                    )
                    device_reg.async_remove_device(device_entry.id)

    # Reload entry to update data
    await hass.config_entries.async_reload(entry.entry_id)
