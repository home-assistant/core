"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

from datetime import datetime

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DIMMER,
    CONF_LEGACY_ENTRY_ID,
    CONF_LIGHT,
    CONF_STRIP,
    CONF_SWITCH,
    DOMAIN,
)

MAC_ADDRESS_LEN = 17


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
    config_entries_by_mac: dict[str, ConfigEntry],
    legacy_entry: ConfigEntry,
) -> None:
    """Migrate the legacy config entries to have an entry per device."""
    entity_registry = er.async_get(hass)
    tplink_reg_entities = er.async_entries_for_config_entry(
        entity_registry, legacy_entry.entry_id
    )

    for reg_entity in tplink_reg_entities:
        # Only migrate entities with a mac address only
        if len(reg_entity.unique_id) != MAC_ADDRESS_LEN:
            continue
        mac = dr.format_mac(reg_entity.unique_id)
        if mac in config_entries_by_mac:
            continue

        domain = (split_entity_id(reg_entity.entity_id))[0]
        if domain not in ("switch", "light"):
            continue
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "migration"},
                data={
                    CONF_LEGACY_ENTRY_ID: reg_entity.config_entry_id,
                    CONF_MAC: mac,
                    CONF_NAME: reg_entity.name
                    or reg_entity.original_name
                    or f"TP-Link device {mac}",
                },
            )
        )

    async def _async_cleanup_legacy_entry(_now: datetime) -> None:
        await async_cleanup_legacy_entry(hass, legacy_entry.entry_id)

    async_call_later(hass, 60, _async_cleanup_legacy_entry)


@callback
def async_migrate_yaml_entries(hass: HomeAssistant, conf: ConfigType) -> None:
    """Migrate yaml to config entries."""
    for device_type in (CONF_LIGHT, CONF_SWITCH, CONF_STRIP, CONF_DIMMER):
        if device_type not in conf:
            continue
        for device in conf[device_type]:
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
    entity_registry = er.async_get(hass)
    tplink_reg_entities = er.async_entries_for_config_entry(
        entity_registry, legacy_entry_id
    )

    for reg_entity in tplink_reg_entities:
        # Only migrate entities with a mac address only
        if len(reg_entity.unique_id) < MAC_ADDRESS_LEN:
            continue
        if dr.format_mac(reg_entity.unique_id[:MAC_ADDRESS_LEN]) == new_entry.unique_id:
            entity_registry._async_update_entity(  # pylint: disable=protected-access
                reg_entity.entity_id, config_entry_id=new_entry.entry_id
            )

    device_registry = dr.async_get(hass)
    tplink_dev_entities = dr.async_entries_for_config_entry(
        device_registry, legacy_entry_id
    )
    for dev_entry in tplink_dev_entities:
        for connection_type, value in dev_entry.connections:
            if (
                connection_type == dr.CONNECTION_NETWORK_MAC
                and value == new_entry.unique_id
            ):
                device_registry._async_update_device(  # pylint: disable=protected-access
                    dev_entry.id, add_config_entry_id=new_entry.entry_id
                )

    hass.config_entries.async_update_entry(
        new_entry,
        data={k: v for k, v in new_entry.data.items() if k != CONF_LEGACY_ENTRY_ID},
    )
