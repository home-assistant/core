"""The Meross Bluetooth integration."""

from __future__ import annotations

import asyncio

from meross_ble import DEFAULT_RETRY_COUNT, MerossModel, create_device

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_MODEL,
    CONF_RETRY_COUNT,
    DATA_BLE_GATT_LOCK,
    DOMAIN,
    LOGGER,
)
from .coordinator import MerossBLEDataUpdateCoordinator

PLATFORMS_BY_MODEL: dict[MerossModel, list[Platform]] = {
    MerossModel.MS120: [
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
    ],
    MerossModel.MS220: [
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
        Platform.EVENT,
    ],
    MerossModel.MS420: [
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    MerossModel.MS700: [
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.EVENT,
    ],
}

type MerossConfigEntry = ConfigEntry[MerossBLEDataUpdateCoordinator]


def _async_ble_gatt_lock(hass: HomeAssistant) -> asyncio.Lock:
    """One shared GATT lock for all Meross BLE devices on this HA instance."""
    store = hass.data.setdefault(DOMAIN, {})
    lock = store.get(DATA_BLE_GATT_LOCK)
    if lock is None:
        lock = asyncio.Lock()
        store[DATA_BLE_GATT_LOCK] = lock
    return lock


def _async_remove_legacy_ble_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Drop retired BLE entities if present from earlier experiments."""
    if entry.unique_id is None:
        return
    registry = er.async_get(hass)
    for domain, unique_suffix in (
        (Platform.BUTTON, "identify"),
        (Platform.SENSOR, "rssi"),
        (Platform.BINARY_SENSOR, "vibration"),
    ):
        entity_id = registry.async_get_entity_id(
            domain, entry.domain, f"{entry.unique_id}-{unique_suffix}"
        )
        if entity_id is not None:
            registry.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: MerossConfigEntry) -> bool:
    """Set up one Meross BLE device from a config entry."""
    assert entry.unique_id is not None
    address: str = entry.data[CONF_ADDRESS]
    model = MerossModel(entry.data[CONF_MODEL])
    # GATT Identify still needs a connectable BLEDevice from the cache.
    gatt_connectable = True
    # False = receive connectable and non-connectable ads. Door/button wake
    # packets are often flagged non-connectable on macOS; True would drop
    # them so Opening never updates after the unavailable watchdog.
    advertisement_connectable = False
    retry_count = entry.options.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT)

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), gatt_connectable
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Meross BLE device with address {address}"
        )

    device = create_device(ble_device, model, retry_count=retry_count)
    coordinator = entry.runtime_data = MerossBLEDataUpdateCoordinator(
        hass,
        LOGGER,
        ble_device,
        device,
        entry.unique_id,
        entry.title,
        advertisement_connectable,
        model,
        entry,
    )
    device.bind_runtime(
        refresh_ble_device=lambda: bluetooth.async_ble_device_from_address(
            hass, address.upper(), True
        ),
        gatt_lock=_async_ble_gatt_lock(hass),
        wait_advertisement=coordinator.async_wait_next_advertisement,
        last_service_info=lambda: bluetooth.async_last_service_info(
            hass, address, connectable=False
        ),
    )
    entry.async_on_unload(coordinator.async_start())
    if not await coordinator.async_wait_ready():
        raise ConfigEntryNotReady(
            f"Meross BLE device {address} not advertising yet; will retry"
        )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS_BY_MODEL[model]
    )
    _async_remove_legacy_ble_entities(hass, entry)
    if model is MerossModel.MS120:
        # Setup / reload only: full firmware history buffer → HA statistics.
        coordinator.history_force_full_resync = True
        coordinator.async_schedule_history_sync()
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: MerossConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MerossConfigEntry) -> bool:
    """Unload a Meross BLE config entry."""
    model = MerossModel(entry.data[CONF_MODEL])
    return await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_MODEL[model]
    )
