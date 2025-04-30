"""Tests for the Rheklo sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.rheklo.coordinator import SCAN_INTERVAL_MINUTES
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(name="platform_sensor", autouse=True)
async def platform_sensor_fixture():
    """Patch Rheklo to only load Sensor platform."""
    with patch("homeassistant.components.rheklo.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    rheklo_config_entry: MockConfigEntry,
    load_rheklo_config_entry: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Rheklo sensors."""
    await snapshot_platform(
        hass, entity_registry, snapshot, rheklo_config_entry.entry_id
    )


async def test_sensor_availability_device_disconnect(
    hass: HomeAssistant,
    generator: dict[str, any],
    mock_rheklo: AsyncMock,
    load_rheklo_config_entry: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Rheklo sensor availability when device is disconnected."""
    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == "Standby"

    generator["device"]["isConnected"] = False

    # Move time to next update
    freezer.tick(SCAN_INTERVAL_MINUTES)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_availability_poll_failure(
    hass: HomeAssistant,
    mock_rheklo: AsyncMock,
    load_rheklo_config_entry: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Rheklo sensor availability when cloud poll fails."""
    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == "Standby"

    mock_rheklo.get_generator_data.side_effect = Exception("Test exception")

    # Move time to next update
    freezer.tick(SCAN_INTERVAL_MINUTES)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE
