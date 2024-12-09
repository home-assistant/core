"""The ohme integration."""

from dataclasses import dataclass
import logging

from ohme import OhmeApiClient

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONFIG_VERSION, ENTITY_TYPES, LEGACY_MAPPING
from .coordinator import (
    OhmeAccountInfoCoordinator,
    OhmeAdvancedSettingsCoordinator,
    OhmeChargeSchedulesCoordinator,
    OhmeChargeSessionsCoordinator,
)

_LOGGER = logging.getLogger(__name__)

type OhmeConfigEntry = ConfigEntry[OhmeConfigEntry]


@dataclass
class OhmeRuntimeData:
    """Store volatile data."""

    client: OhmeApiClient
    coordinators: list[DataUpdateCoordinator]
    slots: list[dict]
    # other_data: dict[str, Any]


async def async_setup_dependencies(hass: core.HomeAssistant, entry: OhmeConfigEntry):
    """Instantiate client and refresh session."""
    client = OhmeApiClient(entry.data["email"], entry.data["password"])

    entry.runtime_data = OhmeRuntimeData(client, [], [])

    await client.async_create_session()
    await client.async_update_device_info()


async def async_update_listener(hass, entry):
    """Handle options flow credentials update."""

    # Reload this instance
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass, entry):
    """Set up Ohme from a config entry."""

    def _update_unique_id(entry: RegistryEntry) -> dict[str, str] | None:
        """Update unique IDs from old format."""
        if entry.unique_id.startswith("ohme_"):
            parts = entry.unique_id.split("_")
            legacy_id = "_".join(parts[2:])

            new_id = LEGACY_MAPPING.get(legacy_id, legacy_id)

            new_id = f"{parts[1]}_{new_id}"

            return {"new_unique_id": new_id}
        return None

    await async_migrate_entries(hass, entry.entry_id, _update_unique_id)

    await async_setup_dependencies(hass, entry)

    coordinators = [
        OhmeChargeSessionsCoordinator(
            hass=hass, config_entry=entry
        ),  # COORDINATOR_CHARGESESSIONS
        OhmeAccountInfoCoordinator(
            hass=hass, config_entry=entry
        ),  # COORDINATOR_ACCOUNTINFO
        OhmeAdvancedSettingsCoordinator(
            hass=hass, config_entry=entry
        ),  # COORDINATOR_ADVANCED
        OhmeChargeSchedulesCoordinator(
            hass=hass, config_entry=entry
        ),  # COORDINATOR_SCHEDULES
    ]

    # We can function without these so setup can continue
    coordinators_optional = [OhmeAdvancedSettingsCoordinator]

    for coordinator in coordinators:
        # Catch failures if this is an 'optional' coordinator
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            allow_failure = False
            for optional in coordinators_optional:
                allow_failure = (
                    True if isinstance(coordinator, optional) else allow_failure
                )

            if allow_failure:
                _LOGGER.error(
                    "%s failed to setup. This coordinator is optional so the integration will still function, but please raise an issue if this persists",
                    coordinator.__class__.__name__,
                )
            else:
                raise

    entry.runtime_data.coordinators = coordinators

    # Setup entities
    await hass.config_entries.async_forward_entry_setups(entry, ENTITY_TYPES)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, ENTITY_TYPES)


async def async_migrate_entry(
    hass: core.HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate old entry."""
    # Version number has gone backwards
    if config_entry.version > CONFIG_VERSION:
        _LOGGER.error("Backwards migration not possible. Please update the integration")
        return False

    # Version number has gone up
    if config_entry.version < CONFIG_VERSION:
        _LOGGER.debug("Migrating from version %s", config_entry.version)
        new_data = config_entry.data

        config_entry.version = CONFIG_VERSION
        hass.config_entries.async_update_entry(config_entry, data=new_data)

        _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True
