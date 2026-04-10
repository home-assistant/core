"""Support for Satel Integra devices."""

import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries

from .client import SatelClient
from .const import (
    CONF_OUTPUT_NUMBER,
    CONF_PARTITION_NUMBER,
    CONF_SWITCHABLE_OUTPUT_NUMBER,
    CONF_ZONE_NUMBER,
    DOMAIN,
    SUBENTRY_TYPE_OUTPUT,
    SUBENTRY_TYPE_PARTITION,
    SUBENTRY_TYPE_SWITCHABLE_OUTPUT,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import (
    SatelConfigEntry,
    SatelIntegraData,
    SatelIntegraOutputsCoordinator,
    SatelIntegraPartitionsCoordinator,
    SatelIntegraZonesCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: SatelConfigEntry) -> bool:
    """Set up  Satel Integra from a config entry."""

    client = SatelClient(hass, entry)

    coordinator_zones = SatelIntegraZonesCoordinator(hass, entry, client)
    coordinator_outputs = SatelIntegraOutputsCoordinator(hass, entry, client)
    coordinator_partitions = SatelIntegraPartitionsCoordinator(hass, entry, client)

    await client.async_connect(
        coordinator_zones.zones_update_callback,
        coordinator_outputs.outputs_update_callback,
        coordinator_partitions.partitions_update_callback,
    )

    entry.runtime_data = SatelIntegraData(
        client=client,
        coordinator_zones=coordinator_zones,
        coordinator_outputs=coordinator_outputs,
        coordinator_partitions=coordinator_partitions,
    )

    async def async_close_connection(event: Event) -> None:
        """Close Satel Integra connection on HA Stop."""
        await client.async_close()

    entry.async_on_unload(entry.add_update_listener(update_listener))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Satel",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SatelConfigEntry) -> bool:
    """Unloading the Satel platforms."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        runtime_data = entry.runtime_data
        await runtime_data.client.async_close()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: SatelConfigEntry) -> None:
    """Handle options update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SatelConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    # 1.2 Migrate subentries to include configured numbers to title
    if config_entry.version == 1 and config_entry.minor_version == 1:
        for subentry in config_entry.subentries.values():
            property_map = {
                SUBENTRY_TYPE_PARTITION: CONF_PARTITION_NUMBER,
                SUBENTRY_TYPE_ZONE: CONF_ZONE_NUMBER,
                SUBENTRY_TYPE_OUTPUT: CONF_OUTPUT_NUMBER,
                SUBENTRY_TYPE_SWITCHABLE_OUTPUT: CONF_SWITCHABLE_OUTPUT_NUMBER,
            }

            new_title = f"{subentry.title} ({subentry.data[property_map[subentry.subentry_type]]})"

            hass.config_entries.async_update_subentry(
                config_entry, subentry, title=new_title
            )

        hass.config_entries.async_update_entry(config_entry, minor_version=2)

    # 2.1 Migrate all entity unique IDs to replace "satel" prefix with config entry ID, allows multiple entries to be configured
    if config_entry.version == 1:

        @callback
        def migrate_unique_id(entity_entry: RegistryEntry) -> dict[str, str]:
            """Migrate the unique ID to a new format."""
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    "satel", config_entry.entry_id
                )
            }

        await async_migrate_entries(hass, config_entry.entry_id, migrate_unique_id)
        hass.config_entries.async_update_entry(config_entry, version=2, minor_version=1)

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
