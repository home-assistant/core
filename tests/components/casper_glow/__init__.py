"""Tests for the Casper Glow integration."""

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)

CASPER_GLOW_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="Jar",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Jar"),
    advertisement=generate_advertisement_data(
        service_uuids=[],
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

SAMSUNG_EARBUDS_ADDRESS = "72:B3:56:C4:12:B7"
SAMSUNG_EARBUDS_NAME = "Evilpigs's Buds2 Pro"
SAMSUNG_EARBUDS_MANUFACTURER_DATA = {
    117: bytes.fromhex(
        "020901000000150300000000000000000000000000000000000000030146015b4865616470686f6e655d20"
    )
}
SAMSUNG_EARBUDS_SERVICE_UUIDS = [
    "0000184e-0000-1000-8000-00805f9b34fb",
    "0000184f-0000-1000-8000-00805f9b34fb",
    "00001850-0000-1000-8000-00805f9b34fb",
    "00001844-0000-1000-8000-00805f9b34fb",
    "0000184d-0000-1000-8000-00805f9b34fb",
]
SAMSUNG_EARBUDS_SERVICE_DATA = {
    "00002b51-0000-1000-8000-00805f9b34fb": bytes.fromhex("2a00"),
    "00001853-0000-1000-8000-00805f9b34fb": bytes.fromhex("00"),
    "0000184e-0000-1000-8000-00805f9b34fb": bytes.fromhex("006f006b0000"),
    "a7a473e9-19c6-491b-aea6-7ea92b8f043a": bytes.fromhex("014652e70e"),
}

SAMSUNG_EARBUDS_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name=SAMSUNG_EARBUDS_NAME,
    address=SAMSUNG_EARBUDS_ADDRESS,
    rssi=-82,
    manufacturer_data=SAMSUNG_EARBUDS_MANUFACTURER_DATA,
    service_uuids=SAMSUNG_EARBUDS_SERVICE_UUIDS,
    service_data=SAMSUNG_EARBUDS_SERVICE_DATA,
    source="local",
    device=generate_ble_device(
        address=SAMSUNG_EARBUDS_ADDRESS, name=SAMSUNG_EARBUDS_NAME
    ),
    advertisement=generate_advertisement_data(
        local_name=SAMSUNG_EARBUDS_NAME,
        manufacturer_data=SAMSUNG_EARBUDS_MANUFACTURER_DATA,
        service_uuids=SAMSUNG_EARBUDS_SERVICE_UUIDS,
        service_data=SAMSUNG_EARBUDS_SERVICE_DATA,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Casper Glow integration."""
    entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, CASPER_GLOW_DISCOVERY_INFO)
    await hass.config_entries.async_setup(entry.entry_id)


NOT_CASPER_GLOW_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="NotGlow",
    address="AA:BB:CC:DD:EE:00",
    rssi=-60,
    manufacturer_data={},
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:00", name="NotGlow"),
    advertisement=generate_advertisement_data(),
    time=0,
    connectable=True,
    tx_power=-127,
)
