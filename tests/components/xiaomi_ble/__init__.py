"""Tests for the SensorPush integration."""

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

NOT_SENSOR_PUSH_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Not it",
    address="00:00:00:00:00:00",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

LYWSDCGQ_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="LYWSDCGQ",
    address="58:2D:34:35:93:21",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-63,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": (
            b"P \xaa\x01\xda!\x9354-X\r\x10\x04\xfe\x00H\x02"
        )
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

MMC_T201_1_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="MMC_T201_1",
    address="00:81:F9:DD:6F:C1",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": (
            b'p"\xdb\x00o\xc1o\xdd\xf9\x81\x00\t\x00 \x05\xc6\rc\rQ'
        )
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

JTYJGD03MI_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="JTYJGD03MI",
    address="54:EF:44:E3:9C:BC",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": (
            b'XY\x97\td\xbc\x9c\xe3D\xefT" `\x88\xfd\x00\x00\x00\x00:\x14\x8f\xb3'
        )
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

YLKG07YL_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="YLKG07YL",
    address="F8:24:41:C5:98:8B",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": (
            b"X0\xb6\x03\xd2\x8b\x98\xc5A$\xf8\xc3I\x14vu~\x00\x00\x00\x99"
        ),
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

HHCCJCY10_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="HHCCJCY10",
    address="DC:23:4D:E5:5B:FC",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={"0000fd50-0000-1000-8000-00805f9b34fb": b"\x0e\x00n\x014\xa4(\x00["},
    service_uuids=["0000fd50-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

MISCALE_V1_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="MISCA",
    address="50:FB:19:1B:B5:DC",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-60,
    manufacturer_data={},
    service_data={
        "0000181d-0000-1000-8000-00805f9b34fb": b"\x22\x9e\x43\xe5\x07\x04\x0b\x10\x13\x01"
    },
    service_uuids=["0000181d-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

MISCALE_V2_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="MIBFS",
    address="50:FB:19:1B:B5:DC",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-60,
    manufacturer_data={},
    service_data={
        "0000181b-0000-1000-8000-00805f9b34fb": b"\x02&\xb2\x07\x05\x04\x0f\x02\x01\xac\x01\x86B"
    },
    service_uuids=["0000181b-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)

MISSING_PAYLOAD_ENCRYPTED = BluetoothServiceInfoBleak(
    name="LYWSD02MMC",
    address="A4:C1:38:56:53:84",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-56,
    manufacturer_data={},
    service_data={
        "0000fe95-0000-1000-8000-00805f9b34fb": b"0X[\x05\x02\x84\x53\x568\xc1\xa4\x08",
    },
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not it"),
    time=0,
    connectable=False,
    tx_power=-127,
)


def make_advertisement(
    address: str, payload: bytes, connectable: bool = True
) -> BluetoothServiceInfoBleak:
    """Make a dummy advertisement."""
    return BluetoothServiceInfoBleak(
        name="Test Device",
        address=address,
        device=generate_ble_device(address, None),
        rssi=-56,
        manufacturer_data={},
        service_data={
            "0000fe95-0000-1000-8000-00805f9b34fb": payload,
        },
        service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
        source="local",
        advertisement=generate_advertisement_data(local_name="Test Device"),
        time=0,
        connectable=connectable,
        tx_power=-127,
    )
