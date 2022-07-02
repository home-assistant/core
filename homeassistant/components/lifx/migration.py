"""Migrate lifx devices to their own config entry."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN


async def async_migrate_legacy_entries(
    hass: HomeAssistant,
    hosts_by_mac: dict[str, str],
    config_entries_by_mac: dict[str, ConfigEntry],
    legacy_entry: ConfigEntry,
) -> bool:
    """Migrate the legacy config entries to have an entry per device."""
    device_registry = dr.async_get(hass)

    for dev_entry in dr.async_entries_for_config_entry(
        device_registry, legacy_entry.entry_id
    ):
        for connection_type, mac in dev_entry.connections:
            if (
                connection_type != dr.CONNECTION_NETWORK_MAC
                or mac in config_entries_by_mac
            ):
                continue
            # await the flows so we only migrrate one at a time
            await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "migration"},
                data={
                    CONF_HOST: hosts_by_mac.get(mac),
                    CONF_MAC: mac,
                    CONF_NAME: dev_entry.name or f"LIFX device {mac}",
                },
            )

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
