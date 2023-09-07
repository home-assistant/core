"""The Airthings BLE integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import re

from airthings_ble import AirthingsBluetoothDeviceData

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import async_get as device_async_get
from homeassistant.helpers.entity_registry import (
    RegistryEntry,
    async_get as entity_async_get,
    async_migrate_entries,
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

    await migrate_unique_id(hass, entry, address)
    update_device_identifiers(hass, entry, address)

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
        identifiers={
            (
                DOMAIN,
                address,
            )
        }
    )
    if device_entry and entry.entry_id in device_entry.config_entries:
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

    @callback
    def async_migrate_callback(entity_entry: RegistryEntry) -> dict | None:
        """Define a callback to migrate Airthings BLE entities to new unique IDs.

        Old: {name}_description.key
        New: {address}_description.key
        """
        _LOGGER.debug("Migrating starting for '%s'", address)

        if entity_entry.unique_id.startswith(address):
            # Already migrated this entity
            return None

        if name := re.sub(r"^.*?_", "", entity_entry.unique_id.lower()):
            new_unique_id = f"{address}_{name}"

            ent_reg = entity_async_get(hass)
            for entity in ent_reg.entities.values():
                if new_unique_id == entity.unique_id:
                    _LOGGER.info(
                        "Could not migrate, entity with unique ID '%s' already exists",
                        new_unique_id,
                    )
                    return None

            if entity_entry.unique_id != new_unique_id:
                return {"new_unique_id": new_unique_id}

        return None

    await async_migrate_entries(hass, entry.entry_id, async_migrate_callback)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
