"""Tests for the Fjäråskupan integration."""


from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

COOKER_SERVICE_INFO = BluetoothServiceInfoBleak(
    name="COOKERHOOD_FJAR",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=BLEDevice(address="AA:BB:CC:DD:EE:FF", name="COOKERHOOD_FJAR"),
    advertisement=AdvertisementData(),
    time=0,
    connectable=True,
)
