"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

from datetime import datetime
from types import MappingProxyType
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DIMMER, CONF_LIGHT, CONF_STRIP, CONF_SWITCH, DOMAIN


async def async_cleanup_legacy_entry(
    hass: HomeAssistant,
    legacy_entry_id: str,
) -> None:
    """Cleanup the legacy entry if the migration is successful."""
    entity_registry = er.async_get(hass)
    if not er.async_entries_for_config_entry(entity_registry, legacy_entry_id):
        await hass.config_entries.async_remove(legacy_entry_id)


@callback
def async_migrate_legacy_entries(
    hass: HomeAssistant,
    hosts_by_mac: dict[str, str],
    config_entries_by_mac: dict[str, ConfigEntry],
    legacy_entry: ConfigEntry,
) -> None:
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
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "migration"},
                    data={
                        CONF_HOST: hosts_by_mac.get(mac),
                        CONF_MAC: mac,
                        CONF_NAME: dev_entry.name or f"TP-Link device {mac}",
                    },
                )
            )

    async def _async_cleanup_legacy_entry(_now: datetime) -> None:
        await async_cleanup_legacy_entry(hass, legacy_entry.entry_id)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_cleanup_legacy_entry)


@callback
def async_migrate_yaml_entries(
    hass: HomeAssistant, conf: ConfigType | MappingProxyType[str, Any]
) -> None:
    """Migrate yaml to config entries."""
    for device_type in (CONF_LIGHT, CONF_SWITCH, CONF_STRIP, CONF_DIMMER):
        for device in conf.get(device_type, []):
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={
                        CONF_HOST: device[CONF_HOST],
                    },
                )
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
