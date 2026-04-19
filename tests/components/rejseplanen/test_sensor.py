"""Test the Rejseplanen sensor."""

from datetime import UTC, datetime, time as Time, timedelta
import logging
from unittest.mock import AsyncMock, MagicMock
import zoneinfo

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rejseplanen.const import DOMAIN
from homeassistant.components.rejseplanen.sensor import (
    DEPARTURE_CLEANUP_BUFFER,
    _get_current_departures,
    _get_delay_minutes,
    _get_departure_timestamp,
    _get_next_departure_cleanup_time,
    async_setup_platform,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .conftest import make_mock_departures

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

LOGGER = logging.getLogger(__name__)

TZ_CPH = zoneinfo.ZoneInfo("Europe/Copenhagen")


@pytest.fixture
def fixed_now():
    """Fixture for a fixed datetime."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen"))


async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test of the sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("stop_id", [123456, 456789, 999999])
def test_get_current_departures(stop_id: int, patch_sensor_now) -> None:
    """Test the _get_current_departures helper function."""

    departures = make_mock_departures(stop_id)
    result = _get_current_departures(departures, TZ_CPH)

    # Only include departures that haven't left yet (with small buffer)
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=TZ_CPH)

    expected = [
        dep
        for dep in departures
        if (ts := _get_departure_timestamp(dep, TZ_CPH))
        and ts > now - DEPARTURE_CLEANUP_BUFFER
    ]

    assert len(result) == len(expected)
    for dep in expected:
        assert dep in result


def test_get_next_departure_cleanup_time_with_mock_api(
    patch_sensor_now, mock_api
) -> None:
    """Test _get_next_departure_cleanup_time using the mock_api for departures."""

    departures = _get_current_departures(
        mock_api.get_filtered_departures(456789), TZ_CPH
    )

    LOGGER.debug(
        "Testing _get_next_departure_cleanup_time with departures from mock_api"
    )

    dep_time = datetime.combine(
        departures[0].rtDate,
        departures[0].rtTime,
        tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen"),
    )
    dep_time += timedelta(seconds=15)

    LOGGER.debug("Combined departure time: %s", dep_time)

    cleanup_time = _get_next_departure_cleanup_time(departures, TZ_CPH)
    assert cleanup_time is not None
    assert cleanup_time == dep_time

    LOGGER.debug("Next cleanup time from mock_api: %s", cleanup_time)
    LOGGER.debug("Departures: %s", departures)

    # Use mock_api to get departures for unknown stop_id (should be None)
    departures = mock_api.get_filtered_departures(999999)
    cleanup_time = _get_next_departure_cleanup_time(departures, TZ_CPH)
    assert cleanup_time is None


def test_get_next_departure_cleanup_time_with_mock_api_edge_cases(
    patch_sensor_now, mock_api
) -> None:
    """Test _get_next_departure_cleanup_time using the mock_api for departures in edge cases."""

    # Test with empty list - should return None
    cleanup_time = _get_next_departure_cleanup_time([], TZ_CPH)
    assert cleanup_time is None

    # Test with departures that have already left (should return None)
    departures = mock_api.get_filtered_departures(123456)
    for dep in departures:
        dep.rtDate = datetime(2024, 1, 1).date()
        dep.rtTime = (datetime(2024, 1, 1, 11, 0, 0) + timedelta(seconds=15)).time()

    cleanup_time = _get_next_departure_cleanup_time(departures, TZ_CPH)
    assert cleanup_time is None


def test_get_departure_timestamp_with_mock_api(patch_sensor_now, mock_api) -> None:
    """Test the _get_departure_timestamp helper function using mock_api departures."""

    # Test with empty list - should return None
    result = _get_departure_timestamp(None, TZ_CPH)
    assert result is None

    # Test with index out of bounds - should return None
    departures = mock_api.get_filtered_departures(123456)

    # Test with valid departure at index 0 - should return realtime timestamp (since mock sets rtTime)
    result = _get_departure_timestamp(departures[0], TZ_CPH)
    assert result is not None
    # Should match the mock's rtDate/rtTime
    expected = datetime.combine(departures[0].rtDate, departures[0].rtTime).replace(
        tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
    )
    assert result == expected

    # Test with valid departure at index 1
    if len(departures) > 1:
        result = _get_departure_timestamp(departures[1], TZ_CPH)
        assert result is not None
        expected = datetime.combine(departures[1].rtDate, departures[1].rtTime).replace(
            tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
        )
        assert result == expected


async def test_async_setup_platform_creates_issue(hass: HomeAssistant) -> None:
    """Test that async_setup_platform creates a deprecation issue."""
    await async_setup_platform(hass, {}, lambda *args, **kwargs: None)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "yaml_deprecated")
    assert issue is not None
    assert issue.translation_key == "yaml_deprecated"


def test_get_delay_minutes_none_departure() -> None:
    """Test _get_delay_minutes returns None when departure is None."""
    result = _get_delay_minutes(None, TZ_CPH)
    assert result is None


def test_get_delay_minutes_no_realtime(mock_api) -> None:
    """Test _get_delay_minutes falls back to planned time when no realtime data."""
    departures = make_mock_departures(123456)
    dep = departures[0]
    # Remove realtime info so _get_departure_timestamp falls back to planned time
    dep.rtDate = None
    dep.rtTime = None

    result = _get_delay_minutes(dep, TZ_CPH)
    # With no realtime, departure uses planned time so delay is 0
    assert result == 0


def test_get_next_departure_cleanup_time_all_in_buffer(patch_sensor_now) -> None:
    """Test returns None when departures are past but within the cleanup buffer."""
    # patch_sensor_now: dt_util.now returns 12:00:00 CET.
    # 11:59:50 CET is 10 seconds before now but inside the 15-second buffer,
    # so _get_current_departures includes them, but none are > now.
    departures = make_mock_departures(123456)  # Returns 2 departures
    for dep in departures:
        dep.rtTime = Time(11, 59, 50)

    result = _get_next_departure_cleanup_time(departures, TZ_CPH)
    assert result is None


async def test_departure_cleanup_trigger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cleanup trigger is scheduled, cancelled on update, and fires at departure time."""
    # Freeze at 10:00 UTC (= 11:00 CET). Coordinator periodic refresh is at 10:05 UTC.
    freezer.move_to(datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC))
    mock_api.calculate_departure_type_bitflag.return_value = 0

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # Departures at 11:01 CET = 10:01 UTC → cleanup_v1 at 10:01:15 UTC.
    departures_v1 = make_mock_departures(123456)
    for dep in departures_v1:
        dep.stopExtId = "123456"  # Match sensor's string stop_id
        dep.rtTime = Time(11, 1, 0)  # 11:01 CET = 10:01 UTC

    mock_board_v1 = MagicMock()
    mock_board_v1.departures = departures_v1

    # First update: _schedule_next_cleanup registers timer. Covers lines 280-290.
    # Use direct assignment + async_update_listeners() to avoid scheduling a
    # coordinator refresh that would cancel the timer before it fires.
    coordinator.data = mock_board_v1
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    # Departures at 11:02 CET = 10:02 UTC → cleanup_v2 at 10:02:15 UTC.
    departures_v2 = make_mock_departures(123456)
    for dep in departures_v2:
        dep.stopExtId = "123456"
        dep.rtTime = Time(11, 2, 0)  # 11:02 CET = 10:02 UTC

    mock_board_v2 = MagicMock()
    mock_board_v2.departures = departures_v2

    # Configure get_departures so any periodic refresh returns v2 data, keeping
    # cleanup_time unchanged and preventing unwanted timer cancellation.
    mock_api.get_departures.return_value = (mock_board_v2, None)

    coordinator.data = mock_board_v2
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    # Advance to 10:02:15 UTC (before coordinator's 10:05 refresh) and fire.
    freezer.move_to(datetime(2024, 1, 1, 10, 2, 15, tzinfo=UTC))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
