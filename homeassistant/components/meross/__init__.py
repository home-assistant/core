"""The Meross Bluetooth integration."""

import asyncio

from meross_ble import DEFAULT_RETRY_COUNT, MerossModel, create_device

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import LOGGER
from .coordinator import MerossBLEDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type MerossConfigEntry = ConfigEntry[MerossBLEDataUpdateCoordinator]

# Shared across all Meross BLE entries: Pi/USB adapters often have 1 connection slot.
_SHARED_LOCKS: dict[str, asyncio.Lock] = {}


def _async_ble_gatt_lock() -> asyncio.Lock:
    """One shared GATT lock for all Meross BLE devices on this HA instance."""
    return _SHARED_LOCKS.setdefault("ble_gatt", asyncio.Lock())


async def async_setup_entry(hass: HomeAssistant, entry: MerossConfigEntry) -> bool:
    """Set up one Meross BLE device from a config entry."""
    assert entry.unique_id is not None
    address: str = entry.data[CONF_ADDRESS]
    model = MerossModel(entry.data[CONF_MODEL])
    # GATT Identify still needs a connectable BLEDevice from the cache.
    gatt_connectable = True
    # False = receive connectable and non-connectable advertisements.
    advertisement_connectable = False

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address.upper(), gatt_connectable
    )
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Meross BLE device with address {address}"
        )

    device = create_device(ble_device, model, retry_count=DEFAULT_RETRY_COUNT)
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
        gatt_lock=_async_ble_gatt_lock(),
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MerossConfigEntry) -> bool:
    """Unload a Meross BLE config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
