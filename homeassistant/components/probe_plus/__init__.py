"""The Probe Plus integration."""

import logging

from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntry

from .coordinator import ProbePlusConfigEntry, ProbePlusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ProbePlusConfigEntry) -> bool:
    """Set up Probe Plus from a config entry."""
    # Perform a migration to ensure the model is added to the config entry schema.
    if CONF_MODEL not in entry.data:
        # The config entry adds the model number of the device to the start of its title
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_MODEL: entry.title.split(" ")[0]}
        )
    coordinator = ProbePlusDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ProbePlusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ProbePlusConfigEntry) -> bool:
    """Migrate a config entry."""
    _LOGGER.debug(
        "Migrating config entry from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    if entry.version > 1:
        return False

    if entry.version == 1 and entry.minor_version == 1:
        mac = entry.unique_id
        if mac is None:
            return True

        legacy_keys = (
            "probe_temperature",
            "probe_battery",
            "probe_voltage",
            "probe_rssi",
        )

        @callback
        def migrate_entity(entity: RegistryEntry) -> dict[str, str] | None:
            """Migrate an entity's unique ID to include the slot number."""
            prefix = f"{mac}_"
            if not entity.unique_id.startswith(prefix):
                return None
            key = entity.unique_id.removeprefix(prefix)
            if key not in legacy_keys:
                return None
            return {"new_unique_id": f"{mac}_{key}_0"}

        await er.async_migrate_entries(hass, entry.entry_id, migrate_entity)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        entry.version,
        entry.minor_version,
    )
    return True
