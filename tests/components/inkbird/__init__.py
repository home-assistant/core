"""Tests for the INKBIRD integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_INKBIRD_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

SPS_SERVICE_INFO = BluetoothServiceInfo(
    name="sps",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    service_data={},
    manufacturer_data={2096: b"\x0f\x12\x00Z\xc7W\x06"},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    source="local",
)

IBBQ_SERVICE_INFO = BluetoothServiceInfo(
    name="iBBQ",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={
        0: b"\x00\x000\xe2\x83}\xb5\x02\xc8\x00\xc8\x00\xc8\x00\xc8\x00"
    },
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)
