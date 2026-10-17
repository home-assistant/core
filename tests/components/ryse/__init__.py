"""Tests for the RYSE BLE integration."""

from collections.abc import Callable

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import HaBluetoothConnector
from homeassistant.components.ryse.const import MANUFACTURER_ID, SERVICE_UUID
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from tests.components.bluetooth import (
    HCI0_SOURCE_ADDRESS,
    FakeRemoteScanner,
    FakeScanner,
    MockBleakClient,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_source,
)

DOMAIN = "ryse"
DEVICE_NAME = "RYSE Shade"
DEVICE_ADDRESS = "AA:BB:CC:DD:EE:FF"
RSSI_VALUE = -40
LOCAL_SOURCE = HCI0_SOURCE_ADDRESS
PROXY_SOURCE = "11:22:33:44:55:66"
PAIRING_MANUFACTURER_DATA = {MANUFACTURER_ID: b"\xcc\x64\x62\x64"}
IDLE_MANUFACTURER_DATA = {MANUFACTURER_ID: b"\x8c\x64\x62\x64"}
USER_INPUT = {CONF_ADDRESS: DEVICE_ADDRESS}


def make_ble_device(name: str | None = DEVICE_NAME) -> BLEDevice:
    """Return a BLEDevice for the test shade."""
    return generate_ble_device(DEVICE_ADDRESS, name)


def make_advertisement(
    *,
    pairing: bool = True,
    name: str | None = DEVICE_NAME,
    manufacturer_data: dict[int, bytes] | None = None,
    service_uuids: list[str] | None = None,
    service_data: dict[str, bytes] | None = None,
) -> AdvertisementData:
    """Return RYSE advertisement data."""
    if manufacturer_data is None:
        manufacturer_data = (
            PAIRING_MANUFACTURER_DATA if pairing else IDLE_MANUFACTURER_DATA
        )
    if service_uuids is None:
        service_uuids = [SERVICE_UUID]
    return generate_advertisement_data(
        local_name=name,
        manufacturer_data=manufacturer_data,
        service_data=service_data or {},
        service_uuids=service_uuids,
        rssi=RSSI_VALUE,
    )


def register_local_scanner(
    hass: HomeAssistant,
    device: BLEDevice,
    advertisement: AdvertisementData,
    source: str = LOCAL_SOURCE,
) -> Callable[[], None]:
    """Register a local adapter scanner that currently sees *device*."""

    class LocalScanner(FakeScanner):
        @property
        def discovered_devices(self) -> list[BLEDevice]:
            return [device]

        @property
        def discovered_devices_and_advertisement_data(
            self,
        ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
            return {device.address: (device, advertisement)}

    scanner = LocalScanner(source, "hci0", connectable=True)
    return bluetooth.async_register_scanner(hass, scanner, connection_slots=5)


def register_remote_scanner(
    hass: HomeAssistant,
) -> tuple[FakeRemoteScanner, Callable[[], None]]:
    """Register a Bluetooth proxy scanner and return it with an unregister callback."""
    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeRemoteScanner(PROXY_SOURCE, "esp32", connector, True)
    unsetup = scanner.async_setup()
    cancel = bluetooth.async_register_scanner(hass, scanner)

    def _unregister() -> None:
        unsetup()
        cancel()

    return scanner, _unregister


def inject_ryse(
    hass: HomeAssistant,
    device: BLEDevice,
    advertisement: AdvertisementData,
    source: str = LOCAL_SOURCE,
) -> None:
    """Inject a RYSE advertisement from *source* into the Bluetooth manager."""
    inject_advertisement_with_source(hass, device, advertisement, source)
