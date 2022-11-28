"""Migrate lifx devices to their own config entry."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import _LOGGER, DOMAIN
from .discovery import async_init_discovery_flow


@callback
def async_migrate_legacy_entries(
    hass: HomeAssistant,
    discovered_hosts_by_serial: dict[str, str],
    existing_serials: set[str],
    legacy_entry: ConfigEntry,
) -> int:
    """Migrate the legacy config entries to have an entry per device."""
    _LOGGER.debug(
        "Migrating legacy entries: discovered_hosts_by_serial=%s, existing_serials=%s",
        discovered_hosts_by_serial,
        existing_serials,
    )

    device_registry = dr.async_get(hass)
    for dev_entry in dr.async_entries_for_config_entry(
        device_registry, legacy_entry.entry_id
    ):
        for domain, serial in dev_entry.identifiers:
            if (
                domain == DOMAIN
                and serial not in existing_serials
                and (host := discovered_hosts_by_serial.get(serial))
            ):
                async_init_discovery_flow(hass, host, serial)

    remaining_devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), legacy_entry.entry_id
    )
    _LOGGER.debug("The following devices remain: %s", remaining_devices)
    return len(remaining_devices)


@callback
def async_migrate_entities_devices(
    hass: HomeAssistant, legacy_entry_id: str, new_entry: ConfigEntry
) -> None:
    """Move entities and devices to the new config entry."""
    migrated_devices = []
    device_registry = dr.async_get(hass)
    for dev_entry in dr.async_entries_for_config_entry(
        device_registry, legacy_entry_id
    ):
        for domain, value in dev_entry.identifiers:
            if domain == DOMAIN and value == new_entry.unique_id:
                _LOGGER.debug(
                    "Migrating device with %s to %s",
                    dev_entry.identifiers,
                    new_entry.unique_id,
                )
                migrated_devices.append(dev_entry.id)
                device_registry.async_update_device(
                    dev_entry.id,
                    add_config_entry_id=new_entry.entry_id,
                    remove_config_entry_id=legacy_entry_id,
                )

    entity_registry = er.async_get(hass)
    for reg_entity in er.async_entries_for_config_entry(
        entity_registry, legacy_entry_id
    ):
        if reg_entity.device_id in migrated_devices:
            entity_registry.async_update_entity(
                reg_entity.entity_id, config_entry_id=new_entry.entry_id
            )
