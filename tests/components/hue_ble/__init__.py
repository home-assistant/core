"""Tests for the HueBLE Bluetooth integration."""

from habluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

TEST_DEVICE_NAME = "Hue Light"
TEST_DEVICE_MAC = "AA:BB:CC:DD:EE:FF"

HUE_BLE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=TEST_DEVICE_NAME,
    manufacturer_data={89: b"\x12\x02\x00\x02"},
    service_data={"0000fe0f-0000-1000-8000-00805f9b34fb": b"\x02\x10\x0e\xbe\x00"},
    service_uuids=[
        "00001800-0000-1000-8000-00805f9b34fb",
        "00001801-0000-1000-8000-00805f9b34fb",
        "0000180a-0000-1000-8000-00805f9b34fb",
        "0000fe0f-0000-1000-8000-00805f9b34fb",
        "932c32bd-0000-47a2-835a-a8d455b859dd",
        "9da2ddf1-0000-44d0-909c-3f3d3cb34a7b",
        "b8843add-0000-4aa1-8794-c3f462030bda",
    ],
    address=TEST_DEVICE_MAC,
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name=TEST_DEVICE_NAME,
        manufacturer_data={89: b"\xfd`0U\x92W"},
        service_data={"0000fe0f-0000-1000-8000-00805f9b34fb": b"\x02\x10\x0e\xbe\x00"},
        service_uuids=[
            "00001800-0000-1000-8000-00805f9b34fb",
            "00001801-0000-1000-8000-00805f9b34fb",
            "0000180a-0000-1000-8000-00805f9b34fb",
            "0000fe0f-0000-1000-8000-00805f9b34fb",
            "932c32bd-0000-47a2-835a-a8d455b859dd",
            "9da2ddf1-0000-44d0-909c-3f3d3cb34a7b",
            "b8843add-0000-4aa1-8794-c3f462030bda",
        ],
    ),
    device=generate_ble_device(TEST_DEVICE_MAC, TEST_DEVICE_NAME),
    time=0,
    connectable=True,
    tx_power=-127,
)

NOT_HUE_BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
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
