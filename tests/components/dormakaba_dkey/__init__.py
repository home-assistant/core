"""Tests for the Dormakaba dKey integration."""
from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data

DKEY_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="00123456",
    address="AA:BB:CC:DD:EE:F0",
    rssi=-60,
    manufacturer_data={},
    service_uuids=["e7a60000-6639-429f-94fd-86de8ea26897"],
    service_data={},
    source="local",
    device=BLEDevice(address="AA:BB:CC:DD:EE:F0", name="00123456"),
    advertisement=generate_advertisement_data(
        service_uuids=["e7a60000-6639-429f-94fd-86de8ea26897"]
    ),
    time=0,
    connectable=True,
)
