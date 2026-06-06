"""The Gardena Bluetooth integration."""

from contextlib import suppress
import logging

from bleak.backends.device import BLEDevice
from gardena_bluetooth.client import CachedConnection, Client
from gardena_bluetooth.const import ScanService
from gardena_bluetooth.parse import ManufacturerData, ProductType
from habluetooth import BluetoothServiceInfoBleak

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
PRODUCTS_SCAN_TIMEOUT = 10
PRODUCT_TYPE_TIMEOUT = 30


async def async_get_product_type(hass: HomeAssistant, address: str) -> ProductType:
    """Get a product type for the given address."""

    data = ManufacturerData()

    def _data_callback(info: BluetoothServiceInfoBleak) -> bool:
        LOGGER.debug("Processing advertisement from %s: %s", info.address, info)
        if info.device.address != address:
            return False

        data.update(info.manufacturer_data.get(ManufacturerData.company, b""))
        return data.product_type is not ProductType.UNKNOWN

    with suppress(TimeoutError):
        await bluetooth.async_process_advertisements(
            hass,
            _data_callback,
            bluetooth.BluetoothCallbackMatcher(
                address=address, manufacturer_id=ManufacturerData.company
            ),
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            timeout=PRODUCT_TYPE_TIMEOUT,
        )
    return data.product_type


async def async_get_products(hass: HomeAssistant) -> dict[str, ManufacturerData]:
    """Get all products that are currently advertising."""
    products: dict[str, ManufacturerData] = {}

    def _data_callback(info: BluetoothServiceInfoBleak) -> bool:
        LOGGER.debug("Processing advertisement from %s: %s", info.address, info)
        if ScanService not in info.service_uuids:
            return False

        raw = info.manufacturer_data.get(ManufacturerData.company, b"")
        if (data := products.get(info.device.address)) is None:
            data = ManufacturerData()
            products[info.device.address] = data

        data.update(raw)
        return False

    with suppress(TimeoutError):
        await bluetooth.async_process_advertisements(
            hass,
            _data_callback,
            bluetooth.BluetoothCallbackMatcher(
                manufacturer_id=ManufacturerData.company
            ),
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            timeout=PRODUCTS_SCAN_TIMEOUT,
        )
    return products


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

    product_type = await async_get_product_type(hass, address)
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
