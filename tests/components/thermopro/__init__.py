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
