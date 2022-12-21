"""Tests for the OralB integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

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
