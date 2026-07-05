"""Tests for the OKOK Scale integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

ADDRESS = "50:FB:19:01:23:45"
TITLE = "OKOK Scale (2345)"

NOT_OKOK_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="00:00:00:00:00:01",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

OKOK_C0_SERVICE_INFO = BluetoothServiceInfo(
    name=ADDRESS,
    address=ADDRESS,
    rssi=-60,
    manufacturer_data={
        61695: b"\x02\x04\xe6\x03\x00\x00\x00\x00\x00\x00\x00\x00P\xfb\x19\xc0\x1cm"
    },
    service_data={},
    service_uuids=[],
    source="local",
)
