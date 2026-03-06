"""Tests for the Casper Glow integration."""

from unittest.mock import AsyncMock, patch

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
    service_uuids=["9bb30001-fee9-4c24-8361-443b5b7c88f6"],
    service_data={},
    source="local",
    device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Jar"),
    advertisement=generate_advertisement_data(
        service_uuids=["9bb30001-fee9-4c24-8361-443b5b7c88f6"],
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Casper Glow integration."""
    entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, CASPER_GLOW_DISCOVERY_INFO)
    with patch("pycasperglow.CasperGlow.query_state", new_callable=AsyncMock):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)


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
