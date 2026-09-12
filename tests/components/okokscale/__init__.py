"""Tests for the OKOK Scale integration."""

from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

NOT_OKOK_SERVICE_INFO = BluetoothServiceInfo(
    name="Not it",
    address="00:00:00:00:00:01",
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

OKOK_F0_ADDRESS = "50:FB:19:01:23:45"
OKOK_F0_TITLE = "OKOK Scale (2345)"
OKOK_F0_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=OKOK_F0_ADDRESS,
    address=OKOK_F0_ADDRESS,
    device=generate_ble_device(OKOK_F0_ADDRESS, OKOK_F0_ADDRESS),
    rssi=-60,
    manufacturer_data={61695: bytes.fromhex("02045403000000000000000050fb19012345")},
    service_data={
        "00002a19-0000-1000-8000-00805f9b34fb": bytes.fromhex("00"),
        "00002a9c-0000-1000-8000-00805f9b34fb": bytes.fromhex(
            "0603e50701300000000000360000000400000000"
        ),
    },
    service_uuids=[
        "00002a19-0000-1000-8000-00805f9b34fb",
        "00002a9c-0000-1000-8000-00805f9b34fb",
    ],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={
            61695: bytes.fromhex("02045403000000000000000050fb19012345")
        },
        service_uuids=[
            "00002a19-0000-1000-8000-00805f9b34fb",
            "00002a9c-0000-1000-8000-00805f9b34fb",
        ],
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

OKOK_20_ADDRESS = "50:FB:19:67:89:AB"
OKOK_20_TITLE = "OKOK Scale (89AB)"
OKOK_20_SERVICE_INFO = BluetoothServiceInfo(
    name=OKOK_20_ADDRESS,
    address=OKOK_20_ADDRESS,
    rssi=-61,
    manufacturer_data={8394: bytes.fromhex("0b41af2f8101051b14be1770c9ed6737a1a873")},
    service_data={},
    service_uuids=[],
    source="local",
)

OKOK_C0_ADDRESS = "80:F4:16:AB:CD:EF"
OKOK_C0_TITLE = "OKOK Scale (CDEF)"
OKOK_C0_SERVICE_INFO = BluetoothServiceInfo(
    name=OKOK_C0_ADDRESS,
    address=OKOK_C0_ADDRESS,
    rssi=-62,
    manufacturer_data={
        11200: bytes.fromhex("064817700a013180f416abcdef"),
        39104: bytes.fromhex("000017700a013080f416abcdef"),
        42688: bytes.fromhex("000017700a013080f416abcdef"),
        53440: bytes.fromhex("000017700a013080f416abcdef"),
        54720: bytes.fromhex("000017700a013080f416abcdef"),
    },
    service_data={},
    service_uuids=[],
    source="local",
)
