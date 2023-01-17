"""Tests for the Airthings BLE integration."""
from __future__ import annotations

from unittest.mock import patch

from airthings_ble import AirthingsBluetoothDeviceData, AirthingsDevice
from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data


def patch_async_setup_entry(return_value=True):
    """Patch async setup entry to return True."""
    return patch(
        "homeassistant.components.airthings_ble.async_setup_entry",
        return_value=return_value,
    )


def patch_async_ble_device_from_address(return_value: BluetoothServiceInfoBleak | None):
    """Patch async ble device from address to return a given value."""
    return patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=return_value,
    )


def patch_airthings_ble(return_value=AirthingsDevice, side_effect=None):
    """Patch airthings-ble device fetcher with given values and effects."""
    return patch.object(
        AirthingsBluetoothDeviceData,
        "update_device",
        return_value=return_value,
        side_effect=side_effect,
    )


WAVE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="cc-cc-cc-cc-cc-cc",
    address="cc:cc:cc:cc:cc:cc",
    rssi=-61,
    manufacturer_data={820: b"\xe4/\xa5\xae\t\x00"},
    service_data={},
    service_uuids=["b42e1c08-ade7-11e4-89d3-123b93f75cba"],
    source="local",
    device=BLEDevice(
        "cc:cc:cc:cc:cc:cc",
        "cc-cc-cc-cc-cc-cc",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data={820: b"\xe4/\xa5\xae\t\x00"},
        service_uuids=["b42e1c08-ade7-11e4-89d3-123b93f75cba"],
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
    device=BLEDevice(
        "cc:cc:cc:cc:cc:cc",
        "unknown",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=[],
    ),
    connectable=True,
    time=0,
)

WAVE_DEVICE_INFO = AirthingsDevice(
    hw_version="REV A",
    sw_version="G-BLE-1.5.3-master+0",
    name="Airthings Wave+",
    identifier="123456",
    sensors={
        "illuminance": 25,
        "battery": 85,
        "humidity": 60.0,
        "radon_1day_avg": 30,
        "radon_longterm_avg": 30,
        "temperature": 21.0,
        "co2": 500.0,
        "voc": 155.0,
        "radon_1day_level": "very low",
        "radon_longterm_level": "very low",
        "pressure": 1020,
    },
    address="cc:cc:cc:cc:cc:cc",
)
