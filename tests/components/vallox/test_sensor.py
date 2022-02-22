"""Tests for Vallox sensor platform."""

from datetime import datetime, timedelta, tzinfo
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .conftest import patch_metrics

from tests.common import MockConfigEntry

ORIG_TZ = dt.DEFAULT_TIME_ZONE


@pytest.fixture(autouse=True)
def reset_tz():
    """Restore the default TZ after test runs."""
    yield
    dt.DEFAULT_TIME_ZONE = ORIG_TZ


@pytest.fixture
def set_tz(request):
    """Set the default TZ to the one requested."""
    return request.getfixturevalue(request.param)


@pytest.fixture
def utc() -> tzinfo:
    """Set the default TZ to UTC."""
    tz = dt.get_time_zone("UTC")
    dt.set_default_time_zone(tz)
    return tz


@pytest.fixture
def helsinki() -> tzinfo:
    """Set the default TZ to Europe/Helsinki."""
    tz = dt.get_time_zone("Europe/Helsinki")
    dt.set_default_time_zone(tz)
    return tz


@pytest.fixture
def new_york() -> tzinfo:
    """Set the default TZ to America/New_York."""
    tz = dt.get_time_zone("America/New_York")
    dt.set_default_time_zone(tz)
    return tz


def _sensor_to_datetime(sensor):
    return datetime.fromisoformat(sensor.state)


def _now_at_13():
    return dt.now().timetz().replace(hour=13, minute=0, second=0, microsecond=0)


async def test_remaining_filter_returns_timestamp(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test that the remaining time for filter sensor returns a timestamp."""
    # Act
    with patch(
        "homeassistant.components.vallox.calculate_next_filter_change_date",
        return_value=dt.now().date(),
    ), patch_metrics(metrics={}):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert sensor.attributes["device_class"] == "timestamp"


async def test_remaining_time_for_filter_none_returned_from_vallox(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test that the remaining time for filter sensor returns 'unknown' when Vallox returns None."""
    # Act
    with patch(
        "homeassistant.components.vallox.calculate_next_filter_change_date",
        return_value=None,
    ), patch_metrics(metrics={}):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert sensor.state == "unknown"


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_time_for_filter_in_the_future(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Test remaining time for filter when Vallox returns a date in the future."""
    # Arrange
    remaining_days = 112
    mocked_filter_end_date = dt.now().date() + timedelta(days=remaining_days)

    # Act
    with patch(
        "homeassistant.components.vallox.calculate_next_filter_change_date",
        return_value=mocked_filter_end_date,
    ), patch_metrics(metrics={}):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_datetime(sensor) == datetime.combine(
        mocked_filter_end_date,
        _now_at_13(),
    )


async def test_remaining_time_for_filter_today(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test remaining time for filter when Vallox returns today."""
    # Arrange
    remaining_days = 0
    mocked_filter_end_date = dt.now().date() + timedelta(days=remaining_days)

    # Act
    with patch(
        "homeassistant.components.vallox.calculate_next_filter_change_date",
        return_value=mocked_filter_end_date,
    ), patch_metrics(metrics={}):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_datetime(sensor) == datetime.combine(
        mocked_filter_end_date,
        _now_at_13(),
    )


async def test_remaining_time_for_filter_in_the_past(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test remaining time for filter when Vallox returns a date in the past."""
    # Arrange
    remaining_days = -3
    mocked_filter_end_date = dt.now().date() + timedelta(days=remaining_days)

    # Act
    with patch(
        "homeassistant.components.vallox.calculate_next_filter_change_date",
        return_value=mocked_filter_end_date,
    ), patch_metrics(metrics={}):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_datetime(sensor) == datetime.combine(
        mocked_filter_end_date,
        _now_at_13(),
    )
