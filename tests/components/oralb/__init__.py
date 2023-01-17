"""Tests for the OralB integration."""

from bleak.backends.device import BLEDevice
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.components.bluetooth import generate_advertisement_data

NOT_ORALB_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

ORALB_SERVICE_INFO = BluetoothServiceInfo(
    name="78:DB:2F:C2:48:BE",
    address="78:DB:2F:C2:48:BE",
    rssi=-63,
    manufacturer_data={220: b"\x02\x01\x08\x03\x00\x00\x00\x01\x01\x00\x04"},
    service_uuids=[],
    service_data={},
    source="local",
)


ORALB_IO_SERIES_4_SERVICE_INFO = BluetoothServiceInfo(
    name="GXB772CD\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    address="78:DB:2F:C2:48:BE",
    rssi=-63,
    manufacturer_data={220: b"\x074\x0c\x038\x00\x00\x02\x01\x00\x04"},
    service_uuids=[],
    service_data={},
    source="local",
)

ORALB_IO_SERIES_6_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Oral-B Toothbrush",
    address="B0:D2:78:20:1D:CF",
    device=BLEDevice("B0:D2:78:20:1D:CF", "Oral-B Toothbrush"),
    rssi=-56,
    manufacturer_data={220: b"\x062k\x02r\x00\x00\x02\x01\x00\x04"},
    service_data={"a0f0ff00-5047-4d53-8208-4f72616c2d42": bytearray(b"1\x00\x00\x00")},
    service_uuids=["a0f0ff00-5047-4d53-8208-4f72616c2d42"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=True,
)
