"""Tests for the Fjäråskupan integration."""


from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

COOKER_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="COOKERHOOD_FJAR",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="COOKERHOOD_FJAR"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
)
