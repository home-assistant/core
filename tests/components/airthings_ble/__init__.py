"""Tests for the Airthings BLE integration."""

from __future__ import annotations

from unittest.mock import patch

from airthings_ble import (
    AirthingsBluetoothDeviceData,
    AirthingsDevice,
    AirthingsDeviceType,
)

from homeassistant.components.airthings_ble.const import DOMAIN
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceRegistry

from tests.common import MockConfigEntry, MockEntity
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device


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


def patch_airthings_device_update():
    """Patch airthings-ble device."""
    return patch(
        "homeassistant.components.airthings_ble.AirthingsBluetoothDeviceData.update_device",
        return_value=WAVE_DEVICE_INFO,
    )


WAVE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="cc-cc-cc-cc-cc-cc",
    address="cc:cc:cc:cc:cc:cc",
    device=generate_ble_device(
        address="cc:cc:cc:cc:cc:cc",
        name="Airthings Wave+",
    ),
    rssi=-61,
    manufacturer_data={820: b"\xe4/\xa5\xae\t\x00"},
    service_data={
        # Sensor data
        "b42e2a68-ade7-11e4-89d3-123b93f75cba": bytearray(
            b"\x01\x02\x03\x04\x00\x05\x00\x06\x00\x07\x00\x08\x00\x09\x00\x0a"
        ),
        # Manufacturer
        "00002a29-0000-1000-8000-00805f9b34fb": bytearray(b"Airthings AS"),
        # Model
        "00002a24-0000-1000-8000-00805f9b34fb": bytearray(b"2930"),
        # Identifier
        "00002a25-0000-1000-8000-00805f9b34fb": bytearray(b"123456"),
        # SW Version
        "00002a26-0000-1000-8000-00805f9b34fb": bytearray(b"G-BLE-1.5.3-master+0"),
        # HW Version
        "00002a27-0000-1000-8000-00805f9b34fb": bytearray(b"REV A"),
        # Command
        "b42e2d06-ade7-11e4-89d3-123b93f75cba": bytearray(b"\x00"),
    },
    service_uuids=[
        "b42e1c08-ade7-11e4-89d3-123b93f75cba",
        "b42e2a68-ade7-11e4-89d3-123b93f75cba",
        "00002a29-0000-1000-8000-00805f9b34fb",
        "00002a24-0000-1000-8000-00805f9b34fb",
        "00002a25-0000-1000-8000-00805f9b34fb",
        "00002a26-0000-1000-8000-00805f9b34fb",
        "00002a27-0000-1000-8000-00805f9b34fb",
        "b42e2d06-ade7-11e4-89d3-123b93f75cba",
    ],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={820: b"\xe4/\xa5\xae\t\x00"},
        service_uuids=["b42e1c08-ade7-11e4-89d3-123b93f75cba"],
    ),
    connectable=True,
    time=0,
    tx_power=0,
)

VIEW_PLUS_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="cc-cc-cc-cc-cc-cc",
    address="cc:cc:cc:cc:cc:cc",
    device=generate_ble_device(
        address="cc:cc:cc:cc:cc:cc",
        name="Airthings View Plus",
    ),
    rssi=-61,
    manufacturer_data={820: b"\xe4/\xa5\xae\t\x00"},
    service_data={
        "b42eb4a6-ade7-11e4-89d3-123b93f75cba": bytearray(
            b"\x01\x02\x03\x04\x00\x05\x00\x06\x00\x07\x00\x08\x00\x09\x00\x0a"
        ),
        # Manufacturer
        "00002a29-0000-1000-8000-00805f9b34fb": bytearray(b"Airthings AS"),
        # Model
        "00002a24-0000-1000-8000-00805f9b34fb": bytearray(b"2960"),
        # Identifier
        "00002a25-0000-1000-8000-00805f9b34fb": bytearray(b"123456"),
        # SW Version
        "00002a26-0000-1000-8000-00805f9b34fb": bytearray(b"A-BLE-1.12.1-master+0"),
        # HW Version
        "00002a27-0000-1000-8000-00805f9b34fb": bytearray(b"REV 1,0"),
    },
    service_uuids=[
        "b42eb4a6-ade7-11e4-89d3-123b93f75cba",
        "b42e90a2-ade7-11e4-89d3-123b93f75cba",
        "b42e2a68-ade7-11e4-89d3-123b93f75cba",
        "00002a29-0000-1000-8000-00805f9b34fb",
        "00002a24-0000-1000-8000-00805f9b34fb",
        "00002a25-0000-1000-8000-00805f9b34fb",
        "00002a26-0000-1000-8000-00805f9b34fb",
        "00002a27-0000-1000-8000-00805f9b34fb",
        "b42e2d06-ade7-11e4-89d3-123b93f75cba",
    ],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={820: b"\xe4/\xa5\xae\t\x00"},
        service_uuids=["b42e90a2-ade7-11e4-89d3-123b93f75cba"],
    ),
    connectable=True,
    time=0,
    tx_power=0,
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
        "cc:cc:cc:cc:cc:cc",
        "unknown",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data={},
        service_uuids=[],
    ),
    connectable=True,
    time=0,
    tx_power=0,
)

WAVE_DEVICE_INFO = AirthingsDevice(
    manufacturer="Airthings AS",
    hw_version="REV A",
    sw_version="G-BLE-1.5.3-master+0",
    model=AirthingsDeviceType.WAVE_PLUS,
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

TEMPERATURE_V1 = MockEntity(
    unique_id="Airthings Wave Plus 123456_temperature",
    name="Airthings Wave Plus 123456 Temperature",
)

HUMIDITY_V2 = MockEntity(
    unique_id="Airthings Wave Plus (123456)_humidity",
    name="Airthings Wave Plus (123456) Humidity",
)

CO2_V1 = MockEntity(
    unique_id="Airthings Wave Plus 123456_co2",
    name="Airthings Wave Plus 123456 CO2",
)

CO2_V2 = MockEntity(
    unique_id="Airthings Wave Plus (123456)_co2",
    name="Airthings Wave Plus (123456) CO2",
)

VOC_V1 = MockEntity(
    unique_id="Airthings Wave Plus 123456_voc",
    name="Airthings Wave Plus 123456 CO2",
)

VOC_V2 = MockEntity(
    unique_id="Airthings Wave Plus (123456)_voc",
    name="Airthings Wave Plus (123456) VOC",
)

VOC_V3 = MockEntity(
    unique_id="cc:cc:cc:cc:cc:cc_voc",
    name="Airthings Wave Plus (123456) VOC",
)


def create_entry(hass):
    """Create a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=WAVE_SERVICE_INFO.address,
        title="Airthings Wave Plus (123456)",
    )
    entry.add_to_hass(hass)
    return entry


def create_device(entry: ConfigEntry, device_registry: DeviceRegistry):
    """Create a device for the given entry."""
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_BLUETOOTH, WAVE_SERVICE_INFO.address)},
        manufacturer="Airthings AS",
        name="Airthings Wave Plus (123456)",
        model="Wave Plus",
    )
