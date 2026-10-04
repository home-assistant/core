"""Tests for the Hase iQ sensors."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyhaseiq import Phase, Status
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hase_iq.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("mock_client")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors while the stove heats up."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_readings_follow_the_phase(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a reading the stove stops reporting becomes unknown."""
    await setup_integration(hass, mock_config_entry)

    mock_client.get_status.return_value = Status(Phase.NOMINAL, performance=69.0)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.hase_iq_phase").state == "nominal"
    assert hass.states.get("sensor.hase_iq_performance").state == "69.0"
    assert hass.states.get("sensor.hase_iq_temperature").state == STATE_UNKNOWN
    assert hass.states.get("sensor.hase_iq_heat_up").state == STATE_UNKNOWN
