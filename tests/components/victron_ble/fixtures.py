"""Fixtures for testing victron_ble."""
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_VICTRON_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_SERVICE_INFO = BluetoothServiceInfo(
    name="Inverter/charger",
    address="01:02:03:04:05:06",
    rssi=-60,
    manufacturer_data={
        0x02E1: bytes.fromhex("100380270c1252dad26f0b8eb39162074d140df410")
    },
    service_data={},
    service_uuids=[],
    source="local",
)

VICTRON_TEST_TOKEN = "DA3F5FA2860CB1CF86BA7A6D1D16B9DD"

VICTRON_TEST_WRONG_TOKEN = "00000000000000000000000000000000"
