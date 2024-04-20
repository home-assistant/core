"""Tests for the BlueMaestro integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_BLUEMAESTRO_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

BLUEMAESTRO_SERVICE_INFO = BluetoothServiceInfo(
    name="FA17B62C",
    manufacturer_data={
        307: b"\x17d\x0e\x10\x00\x02\x00\xf2\x01\xf2\x00\x83\x01\x00\x01\r\x02\xab\x00\xf2\x01\xf2\x01\r\x02\xab\x00\xf2\x01\xf2\x00\xff\x02N\x00\x00\x00\x00\x00"
    },
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    service_data={},
    service_uuids=[],
    source="local",
)
