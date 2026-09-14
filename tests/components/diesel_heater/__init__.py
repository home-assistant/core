"""Tests for the Diesel Heater integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

TEST_ADDRESS = "AA:BB:CC:DD:EE:FF"
TEST_NAME = "Diesel Heater"

DIESEL_HEATER_SERVICE_INFO = BluetoothServiceInfo(
    name=TEST_NAME,
    address=TEST_ADDRESS,
    rssi=-63,
    manufacturer_data={65535: b"\x00\x01"},
    service_data={},
    service_uuids=["0000ffe0-0000-1000-8000-00805f9b34fb"],
    source="local",
)

NOT_DIESEL_HEATER_SERVICE_INFO = BluetoothServiceInfo(
    name="Unknown device",
    address=TEST_ADDRESS,
    rssi=-63,
    manufacturer_data={1234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

# Discovery info that matches only by device name (no service uuid, no mfr id)
DIESEL_HEATER_NAME_ONLY = BluetoothServiceInfo(
    name="VEVOR Air Heater",
    address=TEST_ADDRESS,
    rssi=-63,
    manufacturer_data={1234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

# Discovery info that matches only by manufacturer id 0xFFFF
DIESEL_HEATER_MFR_ID_ONLY = BluetoothServiceInfo(
    name="Anonymous BLE",
    address=TEST_ADDRESS,
    rssi=-63,
    manufacturer_data={65535: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)
