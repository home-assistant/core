"""Test the Ruuvi BLE sensors."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ruuvitag_ble.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from .fixtures import (
    RUUVI_E1_SERVICE_INFO,
    RUUVI_V5_SERVICE_INFO,
    RUUVI_V6_SERVICE_INFO,
)

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("enable_bluetooth", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "service_info",
    [
        pytest.param(RUUVI_E1_SERVICE_INFO, id="e1"),
        pytest.param(RUUVI_V5_SERVICE_INFO, id="v5"),
        pytest.param(RUUVI_V6_SERVICE_INFO, id="v6"),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    service_info: BluetoothServiceInfo,
) -> None:
    """Test the Ruuvi BLE sensors."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=service_info.address)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    inject_bluetooth_service_info(hass, service_info)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
