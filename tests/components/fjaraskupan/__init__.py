"""Tests for the Fjäråskupan integration."""

from fjaraskupan import ANNOUNCE_MANUFACTURER, DEVICE_NAME

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

COOKER_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=DEVICE_NAME,
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=["77a2bd49-1e5a-4961-bba1-21f34fa4bc7b"],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="COOKERHOOD_FJAR"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
    tx_power=-127,
)

COOKER_SERVICE_INFO_DATA = BluetoothServiceInfoBleak(
    name=DEVICE_NAME,
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={ANNOUNCE_MANUFACTURER: b"ODFJAR\x01\x02\x00\x00\x00\x30\x04"},
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name=DEVICE_NAME),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
    tx_power=-127,
)
