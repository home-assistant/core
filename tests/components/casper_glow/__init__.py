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
