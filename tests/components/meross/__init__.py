"""Tests for the Meross Bluetooth integration."""

from home_assistant_bluetooth import BluetoothServiceInfoBleak
from meross_ble.const import (
    MEROSS_SERVICE_DATA_UUID,
    SUBDEV_MS120,
    SUBDEV_MS220,
    SUBDEV_MS420,
    SUBDEV_MS700,
)
from pytest_homeassistant.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
)

MEROSS_MS120_ADDRESS = "AA:BB:CC:DD:EE:FF"
MEROSS_MS220_ADDRESS = "AA:BB:CC:DD:EE:01"
MEROSS_MS420_ADDRESS = "AA:BB:CC:DD:EE:02"
MEROSS_MS700_ADDRESS = "AA:BB:CC:DD:EE:03"

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

_MS420_PAYLOAD = bytes(
    [
        0x01,
        SUBDEV_MS420,
        0x00,
        0x00,
        85,
        0x01,
        0x00,
        0x00,
    ]
)

_MS700_PAYLOAD = bytes(
    [
        0x01,
        SUBDEV_MS700,
        0x00,
        0x00,
        75,
        0x02,
        0x00,
        0x00,
        0x09,
        0xC4,
        0x13,
        0x88,
        0x07,
    ]
)

MEROSS_MS420_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Meross-MS420-EE02",
    address=MEROSS_MS420_ADDRESS,
    device=generate_ble_device(MEROSS_MS420_ADDRESS, "Meross-MS420-EE02"),
    rssi=-52,
    manufacturer_data={},
    service_data={MEROSS_SERVICE_DATA_UUID: _MS420_PAYLOAD},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Meross-MS420-EE02",
        service_data={MEROSS_SERVICE_DATA_UUID: _MS420_PAYLOAD},
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

MEROSS_MS700_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Meross-MS700-EE03",
    address=MEROSS_MS700_ADDRESS,
    device=generate_ble_device(MEROSS_MS700_ADDRESS, "Meross-MS700-EE03"),
    rssi=-48,
    manufacturer_data={},
    service_data={MEROSS_SERVICE_DATA_UUID: _MS700_PAYLOAD},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Meross-MS700-EE03",
        service_data={MEROSS_SERVICE_DATA_UUID: _MS700_PAYLOAD},
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
