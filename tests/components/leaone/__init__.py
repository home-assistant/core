"""Tests for the Leaone integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

SCALE_SERVICE_INFO = BluetoothServiceInfo(
    name="",
    address="5F:5A:5C:52:D3:94",
    rssi=-63,
    manufacturer_data={57280: b"\x06\xa4\x00\x00\x00\x020_Z\\R\xd3\x94"},
    service_uuids=[],
    service_data={},
    source="local",
)
SCALE_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="",
    address="5F:5A:5C:52:D3:94",
    rssi=-63,
    manufacturer_data={
        57280: b"\x06\xa4\x00\x00\x00\x020_Z\\R\xd3\x94",
        63424: b"\x06\xa4\x13\x80\x00\x021_Z\\R\xd3\x94",
    },
    service_uuids=[],
    service_data={},
    source="local",
)
SCALE_SERVICE_INFO_3 = BluetoothServiceInfo(
    name="",
    address="5F:5A:5C:52:D3:94",
    rssi=-63,
    manufacturer_data={
        57280: b"\x06\xa4\x00\x00\x00\x020_Z\\R\xd3\x94",
        63424: b"\x06\xa4\x13\x80\x00\x021_Z\\R\xd3\x94",
        6592: b"\x06\x8e\x00\x00\x00\x020_Z\\R\xd3\x94",
    },
    service_uuids=[],
    service_data={},
    source="local",
)
