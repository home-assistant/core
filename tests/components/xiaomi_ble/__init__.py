"""Tests for the SensorPush integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_SENSOR_PUSH_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

HTW_SERVICE_INFO = BluetoothServiceInfo(
    name="LYWSDCGQ",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b"P \xaa\x01\xda!\x9354-X\r\x10\x04\xfe\x00H\x02"
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
)

HTPWX_SERVICE_INFO = BluetoothServiceInfo(
    name="MMC_T201_1",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b'p"\xdb\x00o\xc1o\xdd\xf9\x81\x00\t\x00 \x05\xc6\rc\rQ'
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
)
