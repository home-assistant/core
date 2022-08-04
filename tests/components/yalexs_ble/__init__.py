"""Tests for the Yale Access Bluetooth integration."""
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

YALE_ACCESS_LOCK_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="M1012LU",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-60,
    manufacturer_data={
        465: b"\x00\x00\xd1\xf0b;\xd8\x1dE\xd6\xba\xeeL\xdd]\xf5\xb2\xe9",
        76: b"\x061\x00Z\x8f\x93\xb2\xec\x85\x06\x00i\x00\x02\x02Q\xed\x1d\xf0",
    },
    service_uuids=[],
    service_data={},
    source="local",
    device=BLEDevice(address="aa:bb:cc:dd:ee:ff", name="M1012LU"),
    advertisement=AdvertisementData(),
)
