"""Tests for the rapt_ble integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

RAPT_MAC = "78:E3:6D:3C:06:66"

NOT_RAPT_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

COMPLETE_SERVICE_INFO = BluetoothServiceInfo(
    name="",
    address=RAPT_MAC,
    rssi=-70,
    manufacturer_data={
        16722: b"PT\x01x\xe3m<\xb9\x94\x94{D|\xc5 47\x02a&\x89*\x83",
        17739: b"G20220612_050156_81c6d14",
    },
    service_data={},
    service_uuids=[],
    source="local",
)

V2_SERVICE_INFO = BluetoothServiceInfo(
    name="",
    address=RAPT_MAC,
    rssi=-70,
    manufacturer_data={
        16722: b"PT\x02\x00\x01\xc1m&\x14\x92kD\x7fR\xc91\xc9\x02-)\x97?F",
        17739: b"G20220612_050156_81c6d14",
    },
    service_data={},
    service_uuids=[],
    source="local",
)

V2_NO_VELOCITY_SERVICE_INFO = BluetoothServiceInfo(
    name="",
    address=RAPT_MAC,
    rssi=-70,
    manufacturer_data={
        16722: b"PT\x02\x00\x00\x00\x00\x00\x00\x94\x8bD|\xb9\xf64E\x02b&w*\xac",
        17739: b"G20220612_050156_81c6d14",
    },
    service_data={},
    service_uuids=[],
    source="local",
)
