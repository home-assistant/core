"""Fixtures for testing RuuviTag BLE."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_RUUVITAG_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

RUUVI_V5_SERVICE_INFO = BluetoothServiceInfo(
    name="RuuviTag 0911",
    address="01:03:05:07:09:11",  # Ignored (the payload encodes the correct MAC)
    rssi=-60,
    manufacturer_data={
        1177: b"\x05\x05\xa0`\xa0\xc8\x9a\xfd4\x02\x8c\xff\x00cvriv\xde\xad{?\xef\xaf"
    },
    service_data={},
    service_uuids=[],
    source="local",
)
RUUVI_V6_SERVICE_INFO = BluetoothServiceInfo(
    name="Ruuvi 1234",
    address="01:03:05:07:12:34",  # Ignored (the payload encodes the correct MAC)
    rssi=-60,
    manufacturer_data={
        1177: b"\x06\x17\x0cVh\xc7\x9e\x00p\x00\xc9\x05\x01\xd9J\xcd\x00L\x88O",
    },
    service_data={},
    service_uuids=[],
    source="local",
)
CONFIGURED_NAME = "RuuviTag EFAF"
CONFIGURED_PREFIX = "ruuvitag_efaf"
