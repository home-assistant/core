"""Tests for the LED BLE Bluetooth integration."""
from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from tests.components.bluetooth import generate_advertisement_data

LED_BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="Triones:F30200000152C",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=BLEDevice(address="AA:BB:CC:DD:EE:FF", name="Triones:F30200000152C"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
)

UNSUPPORTED_LED_BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="LEDnetWFF30200000152C",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=BLEDevice(address="AA:BB:CC:DD:EE:FF", name="LEDnetWFF30200000152C"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
)


NOT_LED_BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="Not",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={
        33: b"\x00\x00\xd1\xf0b;\xd8\x1dE\xd6\xba\xeeL\xdd]\xf5\xb2\xe9",
        21: b"\x061\x00Z\x8f\x93\xb2\xec\x85\x06\x00i\x00\x02\x02Q\xed\x1d\xf0",
    },
    service_uuids=[],
    service_data={},
    source="local",
    device=BLEDevice(address="AA:BB:CC:DD:EE:FF", name="Aug"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
)
