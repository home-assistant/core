"""The Airtouch 5 integration."""

from __future__ import annotations

import logging

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient, AirtouchDevice
from airtouch5py.discovery import AirtouchDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

# device_registry as dr, Maybe needed in migration. If not can be removed later.

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.COVER]

_LOGGER = logging.getLogger(__name__)

type Airtouch5ConfigEntry = ConfigEntry[Airtouch5SimpleClient]


async def async_setup_entry(hass: HomeAssistant, entry: Airtouch5ConfigEntry) -> bool:
    """Set up Airtouch 5 from a config entry."""

    # Create API instance
    host = entry.data[CONF_HOST]

    # So for any device that is created using the old flow (AC_0) is the ID. So we just assume that.
    device = AirtouchDevice(
        host,
        entry.data.get("console_id", ""),
        entry.data.get("model", "AirTouch5"),
        entry.data.get("system_id", 0),
        entry.data.get("name", "Unknown Device"),
    )
    client = Airtouch5SimpleClient(host)
    client.device = device

    # Connect to the API
    try:
        await client.connect_and_stay_connected()
    except TimeoutError as t:
        raise ConfigEntryNotReady from t

    # Store an API object for your platforms to access
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Airtouch5ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = entry.runtime_data
        await client.disconnect()
        client.ac_status_callbacks.clear()
        client.connection_state_callbacks.clear()
        client.data_packet_callbacks.clear()
        client.zone_status_callbacks.clear()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: Airtouch5ConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.minor_version == 1:
        host = entry.data[CONF_HOST]
        try:
            identifier = entry.unique_id
            assert identifier is not None
            AirtouchDiscovery_instance = AirtouchDiscovery()
            await AirtouchDiscovery_instance.establish_server()
            airtouch_device = await AirtouchDiscovery_instance.discover_by_ip(host)
            assert airtouch_device is not None, "Device not found during migration"
            # If for some reason the device is not found during migration, it will fail and will retry next time. This could leave a persistent error if the device cannout route UDP.
        except TimeoutError as exception:
            _LOGGER.error("Error while migrating: %s", exception)
            return False

        # looking for climate entities
        entity_registry = er.async_get(hass)
        for entity in entity_registry.entities.values():
            new_unique_id = None  # initialize
            if entity.platform == DOMAIN:
                if entity.domain == "climate":
                    if entity.unique_id.startswith("zone_"):
                        zone_number = entity.unique_id.split("_")[1]
                        new_unique_id = f"{airtouch_device.system_id}_{zone_number}"
                    elif entity.unique_id.startswith("ac_"):
                        new_unique_id = f"{airtouch_device.system_id}"
                    else:
                        continue
                elif entity.domain == "cover":
                    zone_number = entity.unique_id.split("_")[1]
                    new_unique_id = (
                        f"{airtouch_device.system_id}_{zone_number}_open_percentage"
                    )
                else:
                    continue
                entity_id = entity_registry.async_get_entity_id(
                    entity.domain, DOMAIN, entity.unique_id
                )
                assert entity_id is not None
                entity_entry = entity_registry.async_get(entity_id)
                assert entity_entry is not None
                entity_registry.async_update_entity(
                    entity_entry.entity_id, new_unique_id=new_unique_id
                )
                _LOGGER.debug(
                    "Found entity: %s (unique_id=%s) new ID=%s",
                    entity.entity_id,
                    entity.unique_id,
                    new_unique_id,
                )
        device_registry = dr.async_get(hass)
        for device in device_registry.devices.values():
            if any(d[0] == DOMAIN for d in device.identifiers):
                _LOGGER.debug(
                    "Found device: %s, identifiers=%s",
                    airtouch_device.name,
                    device.identifiers,
                )
                domain, unique_id = next(iter(device.identifiers))
                if domain == "airtouch5":
                    if unique_id.startswith("zone_"):
                        zone_number = unique_id.split("_")[1]
                        new_unique_id = f"{airtouch_device.system_id}_{zone_number}"
                    elif unique_id.startswith("ac_"):
                        new_unique_id = f"{airtouch_device.system_id}"
                    else:
                        continue
                elif domain == "cover":
                    zone_number = unique_id.split("_")[1]
                    new_unique_id = (
                        f"{airtouch_device.system_id}_{zone_number}_open_percentage"
                    )
                else:
                    continue
                device_registry.async_update_device(
                    device.id, new_identifiers={(DOMAIN, new_unique_id)}
                )

        hass.config_entries.async_update_entry(
            entry,
            unique_id=airtouch_device.system_id,
            minor_version=2,
        )
    return True
