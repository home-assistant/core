"""Test the Rejseplanen sensor."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from py_rejseplan.dataclasses.departure import Departure
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rejseplanen.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


def _board(departures: list[Departure]) -> MagicMock:
    """Wrap departures in a mock departure board."""
    board = MagicMock()
    board.departures = departures
    return board


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
@pytest.mark.usefixtures("setup_integration")
async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test of the sensors."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
@pytest.mark.usefixtures("setup_integration")
async def test_past_departures_are_filtered(
    hass: HomeAssistant,
) -> None:
    """Test that departures in the past are not reflected in the state.

    Stop 456789 has a past, a buffer and a future departure but the Gym
    subentry filters on direction "North", leaving only the future one.
    """
    assert hass.states.get("sensor.gym_number_of_departures").state == "1"
    assert hass.states.get("sensor.gym_line").state == "A"
    assert (
        hass.states.get("sensor.gym_departing_in").state == "2024-01-01T11:12:00+00:00"
    )


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
@pytest.mark.usefixtures("setup_integration")
async def test_delay(
    hass: HomeAssistant,
) -> None:
    """Test that the delay is exposed through the delay sensor."""
    # Work: planned 12:05, realtime 12:07 -> 2 minutes delay.
    assert hass.states.get("sensor.work_delayed_by").state == "2"


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
async def test_no_departures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test the sensor states when there are no departures."""
    mock_api.get_departures_async.side_effect = None
    mock_api.get_departures_async.return_value = (_board([]), None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.work_number_of_departures").state == "0"
    assert hass.states.get("sensor.work_line").state == STATE_UNKNOWN


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
@pytest.mark.usefixtures("setup_integration")
async def test_departure_cleanup_trigger(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a departure is dropped once its cleanup time is reached."""
    # Work has departures at 12:07 and 12:08 CET (11:07 and 11:08 UTC).
    assert hass.states.get("sensor.work_number_of_departures").state == "2"
    assert (
        hass.states.get("sensor.work_departing_in").state == "2024-01-01T11:07:00+00:00"
    )

    # Advance just past the first departure + cleanup buffer (15s).
    freezer.tick(timedelta(minutes=7, seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.work_number_of_departures").state == "1"
    assert (
        hass.states.get("sensor.work_departing_in").state == "2024-01-01T11:08:00+00:00"
    )


async def test_async_setup_platform_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that YAML configuration creates a deprecation issue."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": DOMAIN,
                "authentication": "test-api-key",
                "stop_id": 123456,
            }
        },
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_deprecated")
    assert issue is not None
    assert issue.translation_key == "yaml_deprecated"
