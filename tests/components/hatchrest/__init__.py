"""Tests for the hatchrest integration."""
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.hatchrest.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry

VALID_HATCHREST = BluetoothServiceInfoBleak.from_advertisement(
    BLEDevice("00:00:00:00:00:00", "Hatch Baby Rest"),
    AdvertisementData(
        local_name="Hatch Baby Rest",
        address="00:00:00:00:00:00",
        rssi=-50,
        manufacturer_data={1076: b"\x00"},
        service_data={},
        service_uuids=[],
        source="local",
    ),
    source="local",
)

VALID_HATCHREST_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_ADDRESS: VALID_HATCHREST.address,
    },
    unique_id=format_mac(VALID_HATCHREST.address),
)
