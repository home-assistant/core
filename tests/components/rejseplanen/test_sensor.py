"""Test the Rejseplanen sensor."""

from datetime import datetime, timedelta
import logging
from unittest.mock import AsyncMock, patch
import zoneinfo

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rejseplanen.sensor import (
    _calculate_due_in,
    _get_current_departures,
    _get_departure_timestamp,
    _get_next_departure_cleanup_time,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import make_mock_departures

from tests.common import MockConfigEntry, snapshot_platform

LOGGER = logging.getLogger(__name__)


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

    with patch(
        "homeassistant.components.rejseplanen.PLATFORMS",
        [Platform.SENSOR],
    ):
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


def test_calculate_due_in() -> None:
    """Test the _calculate_due_in helper function."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Test departure in 30 minutes
    future_30min = now + timedelta(minutes=30)
    result = _calculate_due_in(future_30min.date(), future_30min.time())
    assert 29 <= result <= 31, f"Expected ~30 minutes, got {result}"

    # Test departure in 1 hour (handles midnight crossing)
    future_1hour = now + timedelta(hours=1)
    result = _calculate_due_in(future_1hour.date(), future_1hour.time())
    assert 59 <= result <= 61, f"Expected ~60 minutes, got {result}"

    # Test departure in the past (should return 0)
    past = now - timedelta(minutes=10)
    result = _calculate_due_in(past.date(), past.time())
    assert result == 0, f"Past departure should return 0, got {result}"

    # Test departure tomorrow (edge case)
    tomorrow = now + timedelta(days=1)
    result = _calculate_due_in(tomorrow.date(), tomorrow.time())
    assert 1439 <= result <= 1441, f"Expected ~1440 minutes (24h), got {result}"


@pytest.mark.parametrize("stop_id", [None, 123456, 456789, 999999])
def test_get_current_departures(stop_id: int, patch_sensor_now) -> None:
    """Test the _get_current_departures helper function."""

    departures = make_mock_departures(stop_id)
    result = _get_current_departures(departures)
    assert len(result) == len(departures)
    for dep in departures:
        assert dep in result


def test_get_next_departure_cleanup_time_with_mock_api(
    patch_sensor_now, mock_api
) -> None:
    """Test _get_next_departure_cleanup_time using the mock_api for departures."""

    # Use mock_api to get departures for stop_id 123456
    departures = mock_api.get_filtered_departures(123456)

    LOGGER.info(
        "Testing _get_next_departure_cleanup_time with departures from mock_api"
    )

    dep_time = datetime.combine(
        departures[0].rtDate,
        departures[0].rtTime,
        tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen"),
    )
    dep_time += timedelta(seconds=15)

    LOGGER.info("Combined departure time: %s", dep_time)

    cleanup_time = _get_next_departure_cleanup_time(departures)
    assert cleanup_time is not None
    assert cleanup_time == dep_time

    LOGGER.info("Next cleanup time from mock_api: %s", cleanup_time)
    LOGGER.info("Departures: %s", departures)

    # Use mock_api to get departures for unknown stop_id (should be None)
    departures = mock_api.get_filtered_departures(999999)
    cleanup_time = _get_next_departure_cleanup_time(departures)
    assert cleanup_time is None


def test_get_departure_timestamp_with_mock_api(patch_sensor_now, mock_api) -> None:
    """Test the _get_departure_timestamp helper function using mock_api departures."""

    # Test with empty list - should return None
    result = _get_departure_timestamp([], 0)
    assert result is None

    # Test with index out of bounds - should return None
    departures = mock_api.get_filtered_departures(123456)
    result = _get_departure_timestamp(departures, 10)  # Out of bounds
    assert result is None

    # Test with valid departure at index 0 - should return realtime timestamp (since mock sets rtTime)
    result = _get_departure_timestamp(departures, 0)
    assert result is not None
    # Should match the mock's rtDate/rtTime
    expected = datetime.combine(departures[0].rtDate, departures[0].rtTime).replace(
        tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
    )
    assert result == expected

    # Test with valid departure at index 1
    if len(departures) > 1:
        result = _get_departure_timestamp(departures, 1)
        assert result is not None
        expected = datetime.combine(departures[1].rtDate, departures[1].rtTime).replace(
            tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
        )
        assert result == expected

    # Test with unknown stop_id (should be empty list, so None)
    departures = mock_api.get_filtered_departures(999999)
    result = _get_departure_timestamp(departures, 0)
    assert result is None
