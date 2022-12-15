"""Tests for the hatchrest integration."""
from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.hatchrest.const import DOMAIN
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data

VALID_HATCHREST = BluetoothServiceInfoBleak(
    name="Hatch Baby Rest",
    address="00:00:00:00:00:00",
    manufacturer_data={1076: b"\x00"},
    service_data={},
    service_uuids=[],
    rssi=-60,
    source="local",
    advertisement=generate_advertisement_data(
        local_name="Hatch Baby Rest",
        manufacturer_data={1076: b"\x00"},
        service_data={},
        service_uuids=[],
    ),
    device=BLEDevice("00:00:00:00:00:00", "Hatch Baby Rest"),
    time=0,
    connectable=True,
)

VALID_HATCHREST_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_ADDRESS: VALID_HATCHREST.address,
    },
    unique_id=format_mac(VALID_HATCHREST.address),
)
