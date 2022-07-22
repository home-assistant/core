"""Tests for the SensorPush integration."""


from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

NOT_SENSOR_PUSH_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="00:00:00:00:00:00",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

LYWSDCGQ_SERVICE_INFO = BluetoothServiceInfo(
    name="LYWSDCGQ",
    address="58:2D:34:35:93:21",
    rssi=-63,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b"P \xaa\x01\xda!\x9354-X\r\x10\x04\xfe\x00H\x02"
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
)

MMC_T201_1_SERVICE_INFO = BluetoothServiceInfo(
    name="MMC_T201_1",
    address="00:81:F9:DD:6F:C1",
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b'p"\xdb\x00o\xc1o\xdd\xf9\x81\x00\t\x00 \x05\xc6\rc\rQ'
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
)
