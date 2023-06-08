"""Tests for the Gardena Bluetooth integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

WATER_TIMER_SERVICE_INFO = BluetoothServiceInfo(
    name="Timer",
    address="00000000-0000-0000-0000-000000000001",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x12\x00\x01"
    },
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)

WATER_TIMER_UNNAMED_SERVICE_INFO = BluetoothServiceInfo(
    name=None,
    address="00000000-0000-0000-0000-000000000002",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x12\x00\x01"
    },
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)

MISSING_SERVICE_SERVICE_INFO = BluetoothServiceInfo(
    name="Missing Service Info",
    address="00000000-0000-0000-0001-000000000000",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x12\x00\x01"
    },
    service_uuids=[],
    source="local",
)

MISSING_MANUFACTURER_DATA_SERVICE_INFO = BluetoothServiceInfo(
    name="Missing Manufacturer Data",
    address="00000000-0000-0000-0001-000000000001",
    rssi=-63,
    service_data={},
    manufacturer_data={},
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)

UNSUPPORTED_GROUP_SERVICE_INFO = BluetoothServiceInfo(
    name="Unsupported Group",
    address="00000000-0000-0000-0001-000000000002",
    rssi=-63,
    service_data={},
    manufacturer_data={
        1062: b"\x02\x07d\x02\x05\x01\x02\x08\x00\x02\t\x01\x04\x06\x10\x00\x01"
    },
    service_uuids=["98bd0001-0b0e-421a-84e5-ddbf75dc6de4"],
    source="local",
)
