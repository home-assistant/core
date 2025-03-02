"""Tests for the Improv via BLE integration."""

from improv_ble_client import SERVICE_DATA_UUID, SERVICE_UUID

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

IMPROV_BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="00123456",
    address="AA:BB:CC:DD:EE:F0",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[SERVICE_UUID],
    service_data={SERVICE_DATA_UUID: b"\x01\x00\x00\x00\x00\x00"},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:F0", name="00123456"),
    advertisement=generate_advertisement_data(
        service_uuids=[SERVICE_UUID],
        service_data={SERVICE_DATA_UUID: b"\x01\x00\x00\x00\x00\x00"},
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)


BAD_IMPROV_BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="00123456",
    address="AA:BB:CC:DD:EE:F0",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[SERVICE_UUID],
    service_data={SERVICE_DATA_UUID: b"\x00\x00\x00\x00\x00\x00"},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:F0", name="00123456"),
    advertisement=generate_advertisement_data(
        service_uuids=[SERVICE_UUID],
        service_data={SERVICE_DATA_UUID: b"\x00\x00\x00\x00\x00\x00"},
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)


PROVISIONED_IMPROV_BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="00123456",
    address="AA:BB:CC:DD:EE:F0",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[SERVICE_UUID],
    service_data={SERVICE_DATA_UUID: b"\x04\x00\x00\x00\x00\x00"},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:F0", name="00123456"),
    advertisement=generate_advertisement_data(
        service_uuids=[SERVICE_UUID],
        service_data={SERVICE_DATA_UUID: b"\x04\x00\x00\x00\x00\x00"},
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)


NOT_IMPROV_BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="Not",
    address="AA:BB:CC:DD:EE:F2",
    rssi=-60,
    manufacturer_data={
        33: b"\x00\x00\xd1\xf0b;\xd8\x1dE\xd6\xba\xeeL\xdd]\xf5\xb2\xe9",
        21: b"\x061\x00Z\x8f\x93\xb2\xec\x85\x06\x00i\x00\x02\x02Q\xed\x1d\xf0",
    },
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:F2", name="Aug"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
    tx_power=-127,
)
