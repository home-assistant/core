"""Tests for the Kegtron integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_KEGTRON_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

KEGTRON_KT100_SERVICE_INFO = BluetoothServiceInfo(
    name="D0:CF:5E:5C:9B:75",
    manufacturer_data={
        65535: b"I\xef\x13\x88\x02\xe2\x01Single Port\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    },
    address="D0:CF:5E:5C:9B:75",
    rssi=-82,
    service_data={},
    service_uuids=[],
    source="local",
)

KEGTRON_KT200_PORT_1_SERVICE_INFO = BluetoothServiceInfo(
    name="D0:CF:5E:5C:9B:75",
    manufacturer_data={
        65535: b"#P\xc3P2\xc8APort 1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    },
    address="D0:CF:5E:5C:9B:75",
    rssi=-82,
    service_uuids=[],
    service_data={},
    source="local",
)

KEGTRON_KT200_PORT_2_SERVICE_INFO = BluetoothServiceInfo(
    name="D0:CF:5E:5C:9B:75",
    manufacturer_data={
        65535: b"\xe62:\x98\x02\xe2Q2nd Port\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    },
    address="D0:CF:5E:5C:9B:75",
    rssi=-82,
    service_uuids=[],
    service_data={},
    source="local",
)
