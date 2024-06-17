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
