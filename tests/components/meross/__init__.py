"""Tests for the Meross Bluetooth integration."""

from home_assistant_bluetooth import BluetoothServiceInfoBleak
from meross_ble.const import MEROSS_SERVICE_DATA_UUID, SUBDEV_MS120, SUBDEV_MS220

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

MEROSS_MS120_ADDRESS = "AA:BB:CC:DD:EE:FF"
MEROSS_MS220_ADDRESS = "AA:BB:CC:DD:EE:01"

_MS120_PAYLOAD = bytes(
    [
        0x01,
        SUBDEV_MS120,
        0x00,
        0x00,
        80,
        0x02,
        0x00,
        0x00,
        0x09,
        0xC4,  # 25.00 C
        0x13,
        0x88,  # 50.00 %
    ]
)

_MS220_PAYLOAD = bytes(
    [
        0x01,
        SUBDEV_MS220,
        0x01,  # door open
        0x00,
        90,
        0x01,
        0x00,
        0x00,
        0x07,  # alarm enable all
    ]
)

MEROSS_MS120_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Meross-MS120-EEFF",
    address=MEROSS_MS120_ADDRESS,
    device=generate_ble_device(MEROSS_MS120_ADDRESS, "Meross-MS120-EEFF"),
    rssi=-50,
    manufacturer_data={},
    service_data={MEROSS_SERVICE_DATA_UUID: _MS120_PAYLOAD},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Meross-MS120-EEFF",
        service_data={MEROSS_SERVICE_DATA_UUID: _MS120_PAYLOAD},
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

MEROSS_MS220_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Meross-MS220-EE01",
    address=MEROSS_MS220_ADDRESS,
    device=generate_ble_device(MEROSS_MS220_ADDRESS, "Meross-MS220-EE01"),
    rssi=-55,
    manufacturer_data={},
    service_data={MEROSS_SERVICE_DATA_UUID: _MS220_PAYLOAD},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Meross-MS220-EE01",
        service_data={MEROSS_SERVICE_DATA_UUID: _MS220_PAYLOAD},
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

NOT_MEROSS_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Not Meross",
    address="11:22:33:44:55:66",
    device=generate_ble_device("11:22:33:44:55:66", "Not Meross"),
    rssi=-60,
    manufacturer_data={1: b"\x00"},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Not Meross",
        manufacturer_data={1: b"\x00"},
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)
