"""Tests for the Aranet4 integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_ARANET4_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

OLD_FIRMWARE_SERVICE_INFO = BluetoothServiceInfo(
    name="Aranet4 12345",
    manufacturer_data={1794: b"\x21\x0a\x04\x00\x00\x00\x00\x00"},
    service_uuids=["f0cd1400-95da-4f4b-9ac8-aa55d312af0c"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    source="local",
)

DISABLED_INTEGRATIONS_SERVICE_INFO = BluetoothServiceInfo(
    name="Aranet4 12345",
    manufacturer_data={1794: b"\x01\x00\x02\x01\x00\x00\x00\x00"},
    service_uuids=["0000fce0-0000-1000-8000-00805f9b34fb"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    source="local",
)

VALID_DATA_SERVICE_INFO = BluetoothServiceInfo(
    name="Aranet4 12345",
    manufacturer_data={
        1794: b'\x21\x00\x02\x01\x00\x00\x00\x01\x8a\x02\xa5\x01\xb1&"Y\x01,\x01\xe8\x00\x88'
    },
    service_uuids=["0000fce0-0000-1000-8000-00805f9b34fb"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    source="local",
)
