"""Tests for the Dormakaba dKey integration."""
from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data

DKEY_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="00123456",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=BLEDevice(address="AA:BB:CC:DD:EE:FF", name="00123456"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
)
