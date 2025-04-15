"""Tests for binary sensor platform."""

from unittest.mock import AsyncMock, patch

from aioautomower.model import MowerActivities, MowerAttributes
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    values: dict[str, MowerAttributes],
) -> None:
    """Test binary sensor states."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("binary_sensor.test_mower_1_charging")
    assert state is not None
    assert state.state == "off"
    state = hass.states.get("binary_sensor.test_mower_1_leaving_dock")
    assert state is not None
    assert state.state == "off"
    state = hass.states.get("binary_sensor.test_mower_1_returning_to_dock")
    assert state is not None
    assert state.state == "off"

    for activity, entity in (
        (MowerActivities.CHARGING, "test_mower_1_charging"),
        (MowerActivities.LEAVING, "test_mower_1_leaving_dock"),
        (MowerActivities.GOING_HOME, "test_mower_1_returning_to_dock"),
    ):
        values[TEST_MOWER_ID].mower.activity = activity
        mock_automower_client.get_status.return_value = values
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        state = hass.states.get(f"binary_sensor.{entity}")
        assert state.state == "on"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test states of the binary sensors."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
