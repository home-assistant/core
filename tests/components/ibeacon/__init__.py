"""Tests for the ibeacon integration."""
from bleak.backends.device import BLEDevice

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

BLUECHARM_BLE_DEVICE = BLEDevice(
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    name="BlueCharm_177999",
)
BLUECHARM_BEACON_SERVICE_INFO = BluetoothServiceInfo(
    name="BlueCharm_177999",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    service_data={},
    manufacturer_data={76: b"\x02\x15BlueCharmBeacons\x0e\xfe\x13U\xc5"},
    service_uuids=[],
    source="local",
)
BLUECHARM_BEACON_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="BlueCharm_177999",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-53,
    manufacturer_data={76: b"\x02\x15BlueCharmBeacons\x0e\xfe\x13U\xc5"},
    service_data={
        "00002080-0000-1000-8000-00805f9b34fb": b"j\x0c\x0e\xfe\x13U",
        "0000feaa-0000-1000-8000-00805f9b34fb": b" \x00\x0c\x00\x1c\x00\x00\x00\x06h\x00\x008\x10",
    },
    service_uuids=["0000feaa-0000-1000-8000-00805f9b34fb"],
    source="local",
)
NO_NAME_BEACON_SERVICE_INFO = BluetoothServiceInfo(
    name="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-53,
    manufacturer_data={76: b"\x02\x15NoNamearmBeacons\x0e\xfe\x13U\xc5"},
    service_data={
        "00002080-0000-1000-8000-00805f9b34fb": b"j\x0c\x0e\xfe\x13U",
        "0000feaa-0000-1000-8000-00805f9b34fb": b" \x00\x0c\x00\x1c\x00\x00\x00\x06h\x00\x008\x10",
    },
    service_uuids=["0000feaa-0000-1000-8000-00805f9b34fb"],
    source="local",
)
BEACON_RANDOM_ADDRESS_SERVICE_INFO = BluetoothServiceInfo(
    name="RandomAddress_1234",
    address="AA:BB:CC:DD:EE:00",
    rssi=-63,
    service_data={},
    manufacturer_data={76: b"\x02\x15RandCharmBeacons\x0e\xfe\x13U\xc5"},
    service_uuids=[],
    source="local",
)
