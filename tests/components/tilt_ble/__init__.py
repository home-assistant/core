"""Tests for the tilt_ble integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_TILT_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

TILT_GREEN_SERVICE_INFO = BluetoothServiceInfo(
    name="F6-0F-28-F2-1F-CB",
    address="F6:0F:28:F2:1F:CB",
    rssi=-70,
    manufacturer_data={
        76: b"\x02\x15\xa4\x95\xbb \xc5\xb1KD\xb5\x12\x13p\xf0-t\xde\x00F\x03\xebR"
    },
    service_data={},
    service_uuids=[],
    source="local",
)
