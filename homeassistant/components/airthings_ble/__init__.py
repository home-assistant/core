"""The Airthings BLE integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import re

from airthings_ble import AirthingsBluetoothDeviceData

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    async_get as device_async_get,
)
from homeassistant.helpers.entity_registry import (
    async_entries_for_device,
    async_get as entity_async_get,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Airthings BLE device from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    address = entry.unique_id

    elevation = hass.config.elevation
    is_metric = hass.config.units is METRIC_SYSTEM
    assert address is not None

    ble_device = bluetooth.async_ble_device_from_address(hass, address)

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Airthings device with address {address}"
        )

    update_device_identifiers(hass, entry, address)
    await migrate_unique_id(hass, entry, address)

    async def _async_update_method():
        """Get data from Airthings BLE."""
        ble_device = bluetooth.async_ble_device_from_address(hass, address)
        airthings = AirthingsBluetoothDeviceData(_LOGGER, elevation, is_metric)

        try:
            data = await airthings.update_device(ble_device)
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_update_method,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def update_device_identifiers(hass: HomeAssistant, entry: ConfigEntry, address: str):
    """Update device identifiers to new identifiers."""
    device_registry = device_async_get(hass)
    device_entry = device_registry.async_get_device(
        connections={
            (
                CONNECTION_BLUETOOTH,
                address,
            )
        }
    )
    if (
        device_entry
        and not device_entry.identifiers
        and entry.entry_id in device_entry.config_entries
    ):
        new_identifiers = {(DOMAIN, address)}
        _LOGGER.debug(
            "Updating device id '%s' with new identifiers '%s'",
            device_entry.id,
            new_identifiers,
        )
        device_registry.async_update_device(
            device_entry.id, new_identifiers=new_identifiers
        )


async def migrate_unique_id(hass: HomeAssistant, entry: ConfigEntry, address: str):
    """Migrate entities to new unique ids (with BLE Address)."""

    _LOGGER.debug("Starting to migrate unique ids for address: %s", address)

    ent_reg = entity_async_get(hass)

    device_registry = device_async_get(hass)
    entity_registry = entity_async_get(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, address)})

    if not device:
        return

    entities = async_entries_for_device(
        entity_registry,
        device_id=device.id,
        include_disabled_entities=True,
    )

    def _migrate_unique_id(entity_id: str, new_unique_id: str):
        _LOGGER.debug(
            "Migrating entity '%s' to unique id '%s'", entity_id, new_unique_id
        )
        ent_reg.async_update_entity(entity_id=entity_id, new_unique_id=new_unique_id)

    unique_ids: dict[str, dict[str, str]] = {}

    for entity in entities:
        # Need to extract the sensor type from the end of the unique id
        if sensor_name := re.sub(r"^.*?_", "", entity.unique_id):
            if sensor_name not in unique_ids:
                unique_ids[sensor_name] = {}
            if entity.unique_id.startswith(address):
                unique_ids[sensor_name]["v3"] = entity.entity_id
            elif "(" in entity.unique_id:
                unique_ids[sensor_name]["v2"] = entity.entity_id
            else:
                unique_ids[sensor_name]["v1"] = entity.entity_id
        else:
            _LOGGER.debug(
                "Could not find sensor name, aborting migration ('%s')",
                entity.unique_id,
            )

    # Go through all the sensors and try to migrate the oldest format first. If it
    # does not exist, try the format introduced in 2023.9.0. Only migrate if the
    # newest correct format does not exist.
    for sensor_type, versions in unique_ids.items():
        if versions.get("v3"):
            # Already migrated, skip this sensor
            continue

        new_unique_id = f"{address}_{sensor_type}"
        if entity_id := versions.get("v1"):
            _migrate_unique_id(
                entity_id=entity_id,
                new_unique_id=new_unique_id,
            )
        elif entity_id := versions.get("v2"):
            _migrate_unique_id(entity_id=entity_id, new_unique_id=new_unique_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
