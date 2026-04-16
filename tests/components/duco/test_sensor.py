"""Tests for the Duco sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from duco.exceptions import DucoConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duco.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> MockConfigEntry:
    """Set up only the sensor platform for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.duco.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_entities_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that sensor entities are created with the correct state."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_iaq_sensor_entities_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that IAQ sensor entities are disabled by default."""
    for entity_id in (
        "sensor.bathroom_rh_humidity_air_quality_index",
        "sensor.office_co2_co2_air_quality_index",
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that sensor entities become unavailable when the coordinator fails."""
    mock_duco_client.async_get_nodes = AsyncMock(
        side_effect=DucoConnectionError("offline")
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.office_co2_carbon_dioxide")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
