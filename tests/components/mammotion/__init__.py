"""Tests for the Mammotion integration."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

BLE_DEVICE_LUBA = BluetoothServiceInfo(
    name="Luba-ABC123",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-38,
    manufacturer_data={},
    service_uuids=["0000ffff-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)

BLE_DEVICE_YUKA = BluetoothServiceInfo(
    name="Yuka-XYZ789",
    address="11:22:33:44:55:66",
    rssi=-45,
    manufacturer_data={},
    service_uuids=["0000ffff-0000-1000-8000-00805f9b34fb"],
    service_data={},
    source="local",
)
