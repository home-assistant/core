"""Tests for the SensorPush integration."""

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

NOT_SENSOR_PUSH_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Not it",
    address="00:00:00:00:00:00",
    device=BLEDevice("00:00:00:00:00:00", None),
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=AdvertisementData(local_name="Not it"),
    time=0,
    connectable=False,
)

LYWSDCGQ_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="LYWSDCGQ",
    address="58:2D:34:35:93:21",
    device=BLEDevice("00:00:00:00:00:00", None),
    rssi=-63,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b"P \xaa\x01\xda!\x9354-X\r\x10\x04\xfe\x00H\x02"
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=AdvertisementData(local_name="Not it"),
    time=0,
    connectable=False,
)

MMC_T201_1_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="MMC_T201_1",
    address="00:81:F9:DD:6F:C1",
    device=BLEDevice("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b'p"\xdb\x00o\xc1o\xdd\xf9\x81\x00\t\x00 \x05\xc6\rc\rQ'
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=AdvertisementData(local_name="Not it"),
    time=0,
    connectable=False,
)

JTYJGD03MI_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="JTYJGD03MI",
    address="54:EF:44:E3:9C:BC",
    device=BLEDevice("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b'XY\x97\td\xbc\x9c\xe3D\xefT" `\x88\xfd\x00\x00\x00\x00:\x14\x8f\xb3'
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=AdvertisementData(local_name="Not it"),
    time=0,
    connectable=False,
)

YLKG07YL_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="YLKG07YL",
    address="F8:24:41:C5:98:8B",
    device=BLEDevice("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b"X0\xb6\x03\xd2\x8b\x98\xc5A$\xf8\xc3I\x14vu~\x00\x00\x00\x99",
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=AdvertisementData(local_name="Not it"),
    time=0,
    connectable=False,
)

MISSING_PAYLOAD_ENCRYPTED = BluetoothServiceInfoBleak(
    name="LYWSD02MMC",
    address="A4:C1:38:56:53:84",
    device=BLEDevice("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b"0X[\x05\x02\x84\x53\x568\xc1\xa4\x08",
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=AdvertisementData(local_name="Not it"),
    time=0,
    connectable=False,
)


def make_advertisement(
    address: str, payload: bytes, connectable: bool = True
) -> BluetoothServiceInfoBleak:
    """Make a dummy advertisement."""
    return BluetoothServiceInfoBleak(
        name="Test Device",
        address=address,
        device=BLEDevice(address, None),
        rssi=-56,
        manufacturer_data={},
        service_data={
            "0000fe95-0000-1000-8000-00805f9b34fb": payload,
        },
        service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
        source="local",
        advertisement=AdvertisementData(local_name="Test Device"),
        time=0,
        connectable=connectable,
    )
