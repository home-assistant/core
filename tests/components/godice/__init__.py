"""Tests for the godice integration."""

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

GODICE_DEVICE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="GoDice_2222_K_v04",
    address="58:2D:34:35:93:21",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-63,
    manufacturer_data={},
    service_data={},
    service_uuids=["0000fe95-0000-1000-8000-00805f9b34fb"],
    source="local",
    advertisement=generate_advertisement_data(local_name="GoDice"),
    time=0,
    connectable=True,
    tx_power=-127,
)

ANOTHER_DEVICE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="Not GoDice",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    device=generate_ble_device("00:00:00:00:00:00", None),
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
    advertisement=generate_advertisement_data(local_name="Not GoDice"),
    time=0,
    connectable=True,
    tx_power=-127,
)
