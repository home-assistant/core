"""The Minecraft Server integration."""

from __future__ import annotations

import logging
from typing import Any

import dns.rdata
import dns.rdataclass
import dns.rdatatype

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

from .api import MinecraftServer, MinecraftServerAddressError, MinecraftServerType
from .const import DOMAIN, KEY_LATENCY, KEY_MOTD
from .coordinator import MinecraftServerCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def load_dnspython_rdata_classes() -> None:
    """Load dnspython rdata classes used by mcstatus."""
    for rdtype in dns.rdatatype.RdataType:
        if not dns.rdatatype.is_metatype(rdtype) or rdtype == dns.rdatatype.OPT:
            dns.rdata.get_rdata_class(dns.rdataclass.IN, rdtype)  # type: ignore[no-untyped-call]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Minecraft Server from a config entry."""

    # Workaround to avoid blocking imports from dnspython (https://github.com/rthalley/dnspython/issues/1083)
    hass.async_add_executor_job(load_dnspython_rdata_classes)

    # Create API instance.
    api = MinecraftServer(
        hass,
        entry.data.get(CONF_TYPE, MinecraftServerType.JAVA_EDITION),
        entry.data[CONF_ADDRESS],
    )

    # Initialize API instance.
    try:
        await api.async_initialize()
    except MinecraftServerAddressError as error:
        raise ConfigEntryNotReady(f"Initialization failed: {error}") from error

    # Create coordinator instance.
    coordinator = MinecraftServerCoordinator(hass, entry.data[CONF_NAME], api)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator instance.
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[entry.entry_id] = coordinator

    # Set up platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Minecraft Server config entry."""

    # Unload platforms.
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # Clean up.
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to a new format."""

    # 1 --> 2: Use config entry ID as base for unique IDs.
    if config_entry.version == 1:
        _LOGGER.debug("Migrating from version 1")

        old_unique_id = config_entry.unique_id
        assert old_unique_id
        config_entry_id = config_entry.entry_id

        # Migrate config entry.
        _LOGGER.debug("Migrating config entry. Resetting unique ID: %s", old_unique_id)
        hass.config_entries.async_update_entry(config_entry, unique_id=None, version=2)

        # Migrate device.
        await _async_migrate_device_identifiers(hass, config_entry, old_unique_id)

        # Migrate entities.
        await er.async_migrate_entries(hass, config_entry_id, _migrate_entity_unique_id)

        _LOGGER.debug("Migration to version 2 successful")

    # 2 --> 3: Use address instead of host and port in config entry.
    if config_entry.version == 2:
        _LOGGER.debug("Migrating from version 2")

        config_data = config_entry.data

        # Migrate config entry.
        address = config_data[CONF_HOST]
        api = MinecraftServer(hass, MinecraftServerType.JAVA_EDITION, address)

        try:
            await api.async_initialize()
            host_only_lookup_success = True
        except MinecraftServerAddressError as error:
            host_only_lookup_success = False
            _LOGGER.debug(
                "Hostname (without port) cannot be parsed, trying again with port: %s",
                error,
            )

        if not host_only_lookup_success:
            address = f"{config_data[CONF_HOST]}:{config_data[CONF_PORT]}"
            api = MinecraftServer(hass, MinecraftServerType.JAVA_EDITION, address)

            try:
                await api.async_initialize()
            except MinecraftServerAddressError:
                _LOGGER.exception(
                    "Can't migrate configuration entry due to error while parsing server address, try again later"
                )
                return False

        _LOGGER.debug(
            "Migrating config entry, replacing host '%s' and port '%s' with address '%s'",
            config_data[CONF_HOST],
            config_data[CONF_PORT],
            address,
        )

        new_data = config_data.copy()
        new_data[CONF_ADDRESS] = address
        del new_data[CONF_HOST]
        del new_data[CONF_PORT]
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=3)

        _LOGGER.debug("Migration to version 3 successful")

    return True


async def _async_migrate_device_identifiers(
    hass: HomeAssistant, config_entry: ConfigEntry, old_unique_id: str | None
) -> None:
    """Migrate the device identifiers to the new format."""
    device_registry = dr.async_get(hass)
    device_entry_found = False
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device_entry.identifiers:
            if identifier[1] == old_unique_id:
                # Device found in registry. Update identifiers.
                new_identifiers = {
                    (
                        DOMAIN,
                        config_entry.entry_id,
                    )
                }
                _LOGGER.debug(
                    "Migrating device identifiers from %s to %s",
                    device_entry.identifiers,
                    new_identifiers,
                )
                device_registry.async_update_device(
                    device_id=device_entry.id, new_identifiers=new_identifiers
                )
                # Device entry found. Leave inner for loop.
                device_entry_found = True
                break

        # Leave outer for loop if device entry is already found.
        if device_entry_found:
            break


@callback
def _migrate_entity_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any]:
    """Migrate the unique ID of an entity to the new format."""

    # Different variants of unique IDs are available in version 1:
    # 1) SRV record: '<host>-srv-<entity_type>'
    # 2) Host & port: '<host>-<port>-<entity_type>'
    # 3) IP address & port: '<mac_address>-<port>-<entity_type>'
    unique_id_pieces = entity_entry.unique_id.split("-")
    entity_type = unique_id_pieces[2]

    # Handle bug in version 1: Entity type names were used instead of
    # keys (e.g. "Protocol Version" instead of "protocol_version").
    new_entity_type = entity_type.lower()
    new_entity_type = new_entity_type.replace(" ", "_")

    # Special case 'MOTD': Name and key differs.
    if new_entity_type == "world_message":
        new_entity_type = KEY_MOTD

    # Special case 'latency_time': Renamed to 'latency'.
    if new_entity_type == "latency_time":
        new_entity_type = KEY_LATENCY

    new_unique_id = f"{entity_entry.config_entry_id}-{new_entity_type}"
    _LOGGER.debug(
        "Migrating entity unique ID from %s to %s",
        entity_entry.unique_id,
        new_unique_id,
    )

    return {"new_unique_id": new_unique_id}
