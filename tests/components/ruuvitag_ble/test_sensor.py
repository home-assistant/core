"""Test the Ruuvitag BLE sensors."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ruuvitag_ble.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .fixtures import RUUVITAG_SERVICE_INFO

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("enable_bluetooth", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the RuuviTag BLE sensors."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=RUUVITAG_SERVICE_INFO.address)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(
        hass,
        RUUVITAG_SERVICE_INFO,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) >= 4

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
