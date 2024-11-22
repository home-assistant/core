"""Platform for the Daikin AC."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientConnectionError
from pydaikin.daikin_base import Appliance
from pydaikin.factory import DaikinFactory

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_UUID,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN, KEY_MAC, TIMEOUT
from .coordinator import DaikinCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with Daikin."""
    conf = entry.data
    # For backwards compat, set unique ID
    if entry.unique_id is None or ".local" in entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=conf[KEY_MAC])

    session = async_get_clientsession(hass)
    host = conf[CONF_HOST]
    try:
        async with asyncio.timeout(TIMEOUT):
            device: Appliance = await DaikinFactory(
                host,
                session,
                key=entry.data.get(CONF_API_KEY),
                uuid=entry.data.get(CONF_UUID),
                password=entry.data.get(CONF_PASSWORD),
            )
        _LOGGER.debug("Connection to %s successful", host)
    except TimeoutError as err:
        _LOGGER.debug("Connection to %s timed out in 60 seconds", host)
        raise ConfigEntryNotReady from err
    except ClientConnectionError as err:
        _LOGGER.debug("ClientConnectionError to %s", host)
        raise ConfigEntryNotReady from err

    coordinator = DaikinCoordinator(hass, device)

    await coordinator.async_config_entry_first_refresh()

    await async_migrate_unique_id(hass, entry, device)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


async def async_migrate_unique_id(
    hass: HomeAssistant, config_entry: ConfigEntry, device: Appliance
) -> None:
    """Migrate old entry."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    old_unique_id = config_entry.unique_id
    new_unique_id = device.mac
    new_mac = dr.format_mac(new_unique_id)
    new_name = device.values.get("name", "Daikin AC")

    @callback
    def _update_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        return update_unique_id(entity_entry, new_unique_id)

    if new_unique_id == old_unique_id:
        return

    duplicate = dev_reg.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, new_mac)}, identifiers=None
    )

    # Remove duplicated device
    if duplicate is not None:
        if config_entry.entry_id in duplicate.config_entries:
            _LOGGER.debug(
                "Removing duplicated device %s",
                duplicate.name,
            )

            # The automatic cleanup in entity registry is scheduled as a task, remove
            # the entities manually to avoid unique_id collision when the entities
            # are migrated.
            duplicate_entities = er.async_entries_for_device(
                ent_reg, duplicate.id, True
            )
            for entity in duplicate_entities:
                if entity.config_entry_id == config_entry.entry_id:
                    ent_reg.async_remove(entity.entity_id)

            dev_reg.async_update_device(
                duplicate.id, remove_config_entry_id=config_entry.entry_id
            )

    # Migrate devices
    for device_entry in dr.async_entries_for_config_entry(
        dev_reg, config_entry.entry_id
    ):
        for connection in device_entry.connections:
            if connection[1] == old_unique_id:
                new_connections = {(CONNECTION_NETWORK_MAC, new_mac)}

                _LOGGER.debug(
                    "Migrating device %s connections to %s",
                    device_entry.name,
                    new_connections,
                )
                dev_reg.async_update_device(
                    device_entry.id,
                    merge_connections=new_connections,
                )

        if device_entry.name is None:
            _LOGGER.debug(
                "Migrating device name to %s",
                new_name,
            )
            dev_reg.async_update_device(
                device_entry.id,
                name=new_name,
            )

        # Migrate entities
        await er.async_migrate_entries(hass, config_entry.entry_id, _update_unique_id)

        new_data = {**config_entry.data, KEY_MAC: dr.format_mac(new_unique_id)}

        hass.config_entries.async_update_entry(
            config_entry, unique_id=new_unique_id, data=new_data
        )


@callback
def update_unique_id(
    entity_entry: er.RegistryEntry, unique_id: str
) -> dict[str, str] | None:
    """Update unique ID of entity entry."""
    if entity_entry.unique_id.startswith(unique_id):
        # Already correct, nothing to do
        return None

    unique_id_parts = entity_entry.unique_id.split("-")
    unique_id_parts[0] = unique_id
    entity_new_unique_id = "-".join(unique_id_parts)

    _LOGGER.debug(
        "Migrating entity %s from %s to new id %s",
        entity_entry.entity_id,
        entity_entry.unique_id,
        entity_new_unique_id,
    )
    return {"new_unique_id": entity_new_unique_id}
