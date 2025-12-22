"""Fixtures for testing Sensirion BLE."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_SENSIRION_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

SENSIRION_SERVICE_INFO_MYCO2 = BluetoothServiceInfo(
    name="MyCO2",
    address="01:03:05:07:09:11",  # Ignored (the payload encodes a device ID)
    rssi=-60,
    manufacturer_data={
        0x06D5: b"\x00\x08\x84\xe3>_3G\xd4\x02",
    },
    service_data={},
    service_uuids=[],
    source="local",
)
CONFIGURED_NAME_MYCO2 = "MyCO2 84E3"
CONFIGURED_PREFIX_MYCO2 = "myco2_84e3"

SENSIRION_SERVICE_INFO_SHT43 = BluetoothServiceInfo(
    name="SHT43 DB",
    address="01:03:05:07:09:12",  # Ignored (the payload encodes a device ID)
    rssi=-60,
    manufacturer_data={
        0x06D5: b"\x00\x06\x3a\xc2\x3c\x61\xf9\x69",
    },
    service_data={},
    service_uuids=[],
    source="local",
)
CONFIGURED_NAME_SHT43 = "SHT43 DB 3AC2"
CONFIGURED_PREFIX_SHT43 = "sht43_db_3ac2"
