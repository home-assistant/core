"""Tests for the Fjäråskupan integration."""


from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import SOURCE_LOCAL, BluetoothServiceInfoBleak

COOKER_SERVICE_INFO = BluetoothServiceInfoBleak.from_advertisement(
    BLEDevice("1.1.1.1", "COOKERHOOD_FJAR"), AdvertisementData(), source=SOURCE_LOCAL
)
