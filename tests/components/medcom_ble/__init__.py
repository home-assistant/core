"""Tests for the Medcom Inspector BLE integration."""
from __future__ import annotations

from unittest.mock import patch

from medcom_ble import MedcomBleDevice, MedcomBleDeviceData

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.medcom_ble.async_setup_entry",
        return_value=return_value,
    )


def patch_async_ble_device_from_address(return_value: BluetoothServiceInfoBleak | None):
    """Patch async ble device from address to return a given value."""
    return patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=return_value,
    )


def patch_medcom_ble(return_value=MedcomBleDevice, side_effect=None):
    """Patch medcom-ble device fetcher with given values and effects."""
    return patch.object(
        MedcomBleDeviceData,
        "update_device",
        return_value=return_value,
        side_effect=side_effect,
    )


MEDCOM_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="InspectorBLE-D9A0",
    address="a0:d9:5a:57:0b:00",
    device=generate_ble_device(
        address="a0:d9:5a:57:0b:00",
        name="InspectorBLE-D9A0",
    ),
    rssi=-54,
    manufacturer_data={},
    service_data={
        # Sensor data
        "d68236af-266f-4486-b42d-80356ed5afb7": bytearray(b" 45,"),
        # Manufacturer
        "00002a29-0000-1000-8000-00805f9b34fb": bytearray(b"International Medcom"),
        # Model
        "00002a24-0000-1000-8000-00805f9b34fb": bytearray(b"Inspector-BLE"),
        # Identifier
        "00002a25-0000-1000-8000-00805f9b34fb": bytearray(b"\xa0\xd9\x5a\x57\x0b\x00"),
        # SW Version
        "00002a26-0000-1000-8000-00805f9b34fb": bytearray(b"170602"),
        # HW Version
        "00002a27-0000-1000-8000-00805f9b34fb": bytearray(b"2.0"),
    },
    service_uuids=[
        "39b31fec-b63a-4ef7-b163-a7317872007f",
        "00002a29-0000-1000-8000-00805f9b34fb",
        "00002a24-0000-1000-8000-00805f9b34fb",
        "00002a25-0000-1000-8000-00805f9b34fb",
        "00002a26-0000-1000-8000-00805f9b34fb",
        "00002a27-0000-1000-8000-00805f9b34fb",
    ],
    source="local",
    advertisement=generate_advertisement_data(
        tx_power=8,
        service_uuids=["39b31fec-b63a-4ef7-b163-a7317872007f"],
    ),
    connectable=True,
    time=0,
)

UNKNOWN_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="unknown",
    address="00:cc:cc:cc:cc:cc",
    rssi=-61,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    device=generate_ble_device(
        "00:cc:cc:cc:cc:cc",
        "unknown",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=[],
    ),
    connectable=True,
    time=0,
)

MEDCOM_DEVICE_INFO = MedcomBleDevice(
    manufacturer="International Medcom",
    hw_version="2.0",
    sw_version="170602",
    model="Inspector BLE",
    model_raw="InspectorBLE-D9A0",
    name="Inspector BLE",
    identifier="a0d95a570b00",
    sensors={
        "cpm": 45,
    },
    address="a0:d9:5a:57:0b:00",
)
