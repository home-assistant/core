"""Tests for Vallox sensor platform."""

from datetime import datetime, timedelta, tzinfo

import pytest
from vallox_websocket_api import MetricData

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def set_tz(request):
    """Set the default TZ to the one requested."""
    request.getfixturevalue(request.param)


@pytest.fixture
def utc(hass: HomeAssistant) -> None:
    """Set the default TZ to UTC."""
    hass.config.set_time_zone("UTC")


@pytest.fixture
def helsinki(hass: HomeAssistant) -> None:
    """Set the default TZ to Europe/Helsinki."""
    hass.config.set_time_zone("Europe/Helsinki")


@pytest.fixture
def new_york(hass: HomeAssistant) -> None:
    """Set the default TZ to America/New_York."""
    hass.config.set_time_zone("America/New_York")


def _sensor_to_datetime(sensor):
    return datetime.fromisoformat(sensor.state)


def _now_at_13():
    return dt_util.now().timetz().replace(hour=13, minute=0, second=0, microsecond=0)


async def test_remaining_time_for_filter_none_returned_from_vallox(
    mock_entry: MockConfigEntry, hass: HomeAssistant, setup_fetch_metric_data_mock
) -> None:
    """Test that the remaining time for filter sensor returns 'unknown' when Vallox returns None."""

    class MockMetricData(MetricData):
        @property
        def next_filter_change_date(self):
            return None

    # Arrange
    setup_fetch_metric_data_mock(metric_data_class=MockMetricData)
    # Act
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert sensor.state == "unknown"


@pytest.mark.parametrize(
    ("remaining_days", "set_tz"),
    [
        (112, "utc"),
        (112, "helsinki"),
        (112, "new_york"),
        (0, "utc"),
        (-3, "utc"),
    ],
    indirect=["set_tz"],
)
async def test_remaining_time_for_filter(
    remaining_days,
    set_tz: tzinfo,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
    setup_fetch_metric_data_mock,
) -> None:
    """Test remaining time for filter when Vallox returns different dates."""
    # Arrange
    mocked_filter_end_date = dt_util.now().date() + timedelta(days=remaining_days)

    class MockMetricData(MetricData):
        @property
        def next_filter_change_date(self):
            return mocked_filter_end_date

    setup_fetch_metric_data_mock(metric_data_class=MockMetricData)

    # Act
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert sensor.attributes["device_class"] == "timestamp"
    assert _sensor_to_datetime(sensor) == datetime.combine(
        mocked_filter_end_date,
        _now_at_13(),
    )


@pytest.mark.parametrize(
    ("metrics", "expected_state"),
    [
        ({"A_CYC_CELL_STATE": 0}, "Heat Recovery"),
        ({"A_CYC_CELL_STATE": 1}, "Cool Recovery"),
        ({"A_CYC_CELL_STATE": 2}, "Bypass"),
        ({"A_CYC_CELL_STATE": 3}, "Defrosting"),
        ({"A_CYC_CELL_STATE": 4}, "unknown"),
    ],
)
async def test_cell_state_sensor(
    metrics,
    expected_state,
    mock_entry: MockConfigEntry,
    hass: HomeAssistant,
    setup_fetch_metric_data_mock,
) -> None:
    """Test cell state sensor in different states."""
    # Arrange
    setup_fetch_metric_data_mock(metrics=metrics)

    # Act
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_cell_state")
    assert sensor.state == expected_state
