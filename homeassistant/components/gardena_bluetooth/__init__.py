"""The Gardena Bluetooth integration."""

import logging

from bleak.backends.device import BLEDevice
from gardena_bluetooth.client import CachedConnection, Client
from gardena_bluetooth.const import ProductType
from gardena_bluetooth.scan import async_get_manufacturer_data

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import (
    DeviceUnavailable,
    GardenaBluetoothConfigEntry,
    GardenaBluetoothCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.VALVE,
]
LOGGER = logging.getLogger(__name__)
DISCONNECT_DELAY = 5


def get_connection(hass: HomeAssistant, address: str) -> CachedConnection:
    """Set up a cached client that keeps connection after last use."""

    def _device_lookup() -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        )
        if not device:
            raise DeviceUnavailable("Unable to find device")
        return device

    return CachedConnection(DISCONNECT_DELAY, _device_lookup)


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenaBluetoothConfigEntry
) -> bool:
    """Set up Gardena Bluetooth from a config entry."""

    address = entry.data[CONF_ADDRESS]

    try:
        mfg_data = await async_get_manufacturer_data({address})
    except TimeoutError as exc:
        raise ConfigEntryNotReady("Unable to find product type") from exc

    product_type = mfg_data[address].product_type
    if product_type is ProductType.UNKNOWN:
        raise ConfigEntryNotReady("Unable to find product type")

    client = Client(get_connection(hass, address), product_type)

    coordinator = GardenaBluetoothCoordinator(
        hass,
        entry,
        LOGGER,
        client,
        address,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_request_refresh()
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GardenaBluetoothConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
