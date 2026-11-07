"""Test measurement semantics and push availability."""

import asyncio
from dataclasses import replace

from aioelecway import StorageData, Telemetry
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import DATA, SERIAL

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("mock_client")


async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot all entities, units, statistics classes and stable identities."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
    device = device_registry.async_get_device_by_identifier(
        ("elecway", SERIAL), config_entry.entry_id
    )
    assert device is not None
    assert device.model == DATA.model
    assert device.serial_number == SERIAL


async def test_push_updates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    updates: asyncio.Queue[StorageData | None],
) -> None:
    """Offline becomes unavailable; recovery preserves zero versus unknown."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = f"sensor.elecway_{SERIAL.lower()}_output_power"
    assert hass.states.get(entity_id).state == "797.3"
    updates.put_nowait(None)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    updates.put_nowait(replace(DATA, telemetry=Telemetry(output_power=0)))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "0"
    assert (
        hass.states.get(f"sensor.elecway_{SERIAL.lower()}_pv_power").state
        == STATE_UNKNOWN
    )
