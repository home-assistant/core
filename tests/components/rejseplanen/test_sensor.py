"""Test the Rejseplanen sensor."""

from datetime import datetime, timedelta
import logging
from unittest.mock import AsyncMock, patch
import zoneinfo

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rejseplanen.sensor import (
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

    with patch(
        "homeassistant.components.rejseplanen.PLATFORMS",
        [Platform.SENSOR],
    ):
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize("stop_id", [123456, 456789, 999999])
def test_get_current_departures(stop_id: int, patch_sensor_now) -> None:
    """Test the _get_current_departures helper function."""

    departures = make_mock_departures(stop_id)
    result = _get_current_departures(
        departures,
        TZ_CPH,
    )
    assert len(result) == len(departures)
    for dep in departures:
        assert dep in result


def test_get_next_departure_cleanup_time_with_mock_api(
    patch_sensor_now, mock_api
) -> None:
    """Test _get_next_departure_cleanup_time using the mock_api for departures."""

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

    cleanup_time = _get_next_departure_cleanup_time(departures, TZ_CPH)
    assert cleanup_time is not None
    assert cleanup_time == dep_time

    LOGGER.info("Next cleanup time from mock_api: %s", cleanup_time)
    LOGGER.info("Departures: %s", departures)

    # Use mock_api to get departures for unknown stop_id (should be None)
    departures = mock_api.get_filtered_departures(999999)
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
