"""Migrate lifx devices to their own config entry."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .discovery import async_init_discovery_flow


def async_get_device_entry(
    hass: HomeAssistant, legacy_entry: ConfigEntry, existing_macs: set[str]
) -> tuple[dr.DeviceEntry | None, str | None]:
    """Return the device entry for a given mac."""
    device_registry = dr.async_get(hass)
    for dev_entry in dr.async_entries_for_config_entry(
        device_registry, legacy_entry.entry_id
    ):
        for connection_type, mac in dev_entry.connections:
            if connection_type != dr.CONNECTION_NETWORK_MAC or mac in existing_macs:
                continue
            return dev_entry, mac
    return None, None


async def async_migrate_legacy_entries(
    hass: HomeAssistant,
    discovered_hosts_by_mac: dict[str, str],
    existing_macs: set[str],
    legacy_entry: ConfigEntry,
) -> bool:
    """Migrate the legacy config entries to have an entry per device."""
    dev_entry, mac = async_get_device_entry(hass, legacy_entry, existing_macs)
    # await the flows so we only migrrate one at a time
    if dev_entry and mac:
        await async_init_discovery_flow(hass, discovered_hosts_by_mac[mac])

    return not er.async_entries_for_config_entry(
        er.async_get(hass), legacy_entry.entry_id
    )


async def async_migrate_entities_devices(
    hass: HomeAssistant, legacy_entry_id: str, new_entry: ConfigEntry
) -> None:
    """Move entities and devices to the new config entry."""
    migrated_devices = []
    device_registry = dr.async_get(hass)
    for dev_entry in dr.async_entries_for_config_entry(
        device_registry, legacy_entry_id
    ):
        for connection_type, value in dev_entry.connections:
            if (
                connection_type == dr.CONNECTION_NETWORK_MAC
                and value == new_entry.unique_id
            ):
                migrated_devices.append(dev_entry.id)
                device_registry.async_update_device(
                    dev_entry.id, add_config_entry_id=new_entry.entry_id
                )

    entity_registry = er.async_get(hass)
    for reg_entity in er.async_entries_for_config_entry(
        entity_registry, legacy_entry_id
    ):
        if reg_entity.device_id in migrated_devices:
            entity_registry.async_update_entity(
                reg_entity.entity_id, config_entry_id=new_entry.entry_id
            )
