"""Tests for the ThermoPro integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_THERMOPRO_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)


TP357_SERVICE_INFO = BluetoothServiceInfo(
    name="TP357 (2142)",
    manufacturer_data={61890: b"\x00\x1d\x02,"},
    service_uuids=[],
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-60,
    service_data={},
    source="local",
)

TP358_SERVICE_INFO = BluetoothServiceInfo(
    name="TP358 (4221)",
    manufacturer_data={61890: b"\x00\x1d\x02,"},
    service_uuids=[],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-65,
    service_data={},
    source="local",
)

TP962R_SERVICE_INFO = BluetoothServiceInfo(
    name="TP962R (0000)",
    manufacturer_data={14081: b"\x00;\x0b7\x00"},
    service_uuids=["72fbb631-6f6b-d1ba-db55-2ee6fdd942bd"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-52,
    service_data={},
    source="local",
)

TP962R_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="TP962R (0000)",
    manufacturer_data={17152: b"\x00\x17\nC\x00", 14081: b"\x00;\x0b7\x00"},
    service_uuids=["72fbb631-6f6b-d1ba-db55-2ee6fdd942bd"],
    address="aa:bb:cc:dd:ee:ff",
    rssi=-52,
    service_data={},
    source="local",
)
