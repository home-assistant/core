"""The Airtouch 5 integration."""

from __future__ import annotations

import logging

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient
from airtouch5py.discovery import AirtouchDevice, AirtouchDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.info(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )
    if config_entry.version == 1:
        host = config_entry.data[CONF_HOST]

        airtouchDiscovery_instance = AirtouchDiscovery()
        await airtouchDiscovery_instance.establish_server()
        airtouch_devices = await airtouchDiscovery_instance.discover(host)

        if airtouch_devices is not None:
            airtouch_device = airtouch_devices[0]
            new_unique_device_id = str(airtouch_device.system_id)

            # Migrate entity unique IDs
            ent_reg = er.async_get(hass)
            for entity_id, entity in list(ent_reg.entities.items()):
                if entity.config_entry_id != config_entry.entry_id:
                    continue
                _LOGGER.debug("Migrating entity_id: %s", entity_id)

                old_unique_id = entity.unique_id

                if old_unique_id.startswith("ac_"):
                    new_unique_id = f"ac_{airtouch_device.system_id}"
                    ent_reg.async_update_entity(
                        entity_id,
                        new_unique_id=new_unique_id,
                    )

                elif old_unique_id.startswith("zone_"):
                    if old_unique_id.endswith("_open_percentage"):
                        zone_number = old_unique_id.split("_")[1]
                        new_unique_id = (
                            f"{airtouch_device.system_id}_{zone_number}_open_percentage"
                        )
                    else:
                        zone_number = old_unique_id.split("_")[1]
                        new_unique_id = (
                            f"zone_{airtouch_device.system_id}_{zone_number}"
                        )
                    ent_reg.async_update_entity(
                        entity_id,
                        new_unique_id=new_unique_id,
                    )
                else:
                    _LOGGER.warning(
                        "Unknown unique_id format during migration: %s", old_unique_id
                    )
                    continue

            dev_reg = dr.async_get(hass)
            for device in list(dev_reg.devices.values()):
                if config_entry.entry_id in device.config_entries:
                    has_entities = any(
                        e.device_id == device.id for e in ent_reg.entities.values()
                    )
                    if not has_entities:
                        _LOGGER.info("Removing unused device: %s", device.name)
                        dev_reg.async_remove_device(device.id)

            # Migrate device info
            new_data = {**config_entry.data}
            new_data.update(
                {
                    "name": airtouch_device.name,
                    "model": airtouch_device.model,
                    "console_id": airtouch_device.console_id,
                    "system_id": airtouch_device.system_id,
                    "host": airtouch_device.ip,
                }
            )

            hass.config_entries.async_update_entry(
                config_entry,
                data=new_data,
                minor_version=0,
                version=2,
                unique_id=new_unique_device_id,
            )

    _LOGGER.info(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )
    return True
