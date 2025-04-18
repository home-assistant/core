"""Tests for the KEM sensors."""

from __future__ import annotations

from datetime import timedelta

from aiokem import AioKem
from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.kem.const import SCAN_INTERVAL_MINUTES
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    platform_sensor,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    kem_config_entry: MockConfigEntry,
    mock_kem: AioKem,
) -> None:
    """Test the KEM sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, kem_config_entry.entry_id)


async def test_sensor_availability(
    hass: HomeAssistant,
    platform_sensor,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    kem_config_entry: MockConfigEntry,
    generator: dict[str, any],
    mock_kem: AioKem,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the KEM sensors."""
    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == "Standby"

    generator["device"]["isConnected"] = False

    # Move time to next update
    freezer.tick(timedelta(minutes=SCAN_INTERVAL_MINUTES))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE

    generator["device"]["isConnected"] = True

    mock_kem.get_generator_data.side_effect = Exception("Test exception")

    # Move time to next update
    freezer.tick(timedelta(minutes=SCAN_INTERVAL_MINUTES))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE
