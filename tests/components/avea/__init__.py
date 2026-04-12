"""Tests for the Avea integration."""

from homeassistant.components.avea.const import AVEA_SERVICE_UUID
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

AVEA_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="Avea Bulb",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[AVEA_SERVICE_UUID],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Avea Bulb"),
    advertisement=generate_advertisement_data(
        local_name="Avea Bulb",
        manufacturer_data={},
        service_data={},
        service_uuids=[AVEA_SERVICE_UUID],
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

NOT_AVEA_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="Plain Bulb",
    address="11:22:33:44:55:66",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(address="11:22:33:44:55:66", name="Plain Bulb"),
    advertisement=generate_advertisement_data(
        local_name="Plain Bulb",
        manufacturer_data={},
        service_data={},
        service_uuids=[],
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)
