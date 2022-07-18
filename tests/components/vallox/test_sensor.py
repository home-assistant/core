"""Tests for Vallox sensor platform."""

from datetime import datetime, timedelta, tzinfo
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .conftest import patch_metrics

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
    return dt.now().timetz().replace(hour=13, minute=0, second=0, microsecond=0)


async def test_remaining_filter_returns_timestamp(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test that the remaining time for filter sensor returns a timestamp."""
    # Act
    with patch(
        "homeassistant.components.vallox._api_get_next_filter_change_date",
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
        "homeassistant.components.vallox._api_get_next_filter_change_date",
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
        "homeassistant.components.vallox._api_get_next_filter_change_date",
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
        "homeassistant.components.vallox._api_get_next_filter_change_date",
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
        "homeassistant.components.vallox._api_get_next_filter_change_date",
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


async def test_cell_state_sensor_heat_recovery(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test cell state sensor in heat recovery state."""
    # Arrange
    metrics = {"A_CYC_CELL_STATE": 0}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_cell_state")
    assert sensor.state == "Heat Recovery"


async def test_cell_state_sensor_cool_recovery(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test cell state sensor in cool recovery state."""
    # Arrange
    metrics = {"A_CYC_CELL_STATE": 1}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_cell_state")
    assert sensor.state == "Cool Recovery"


async def test_cell_state_sensor_bypass(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test cell state sensor in bypass state."""
    # Arrange
    metrics = {"A_CYC_CELL_STATE": 2}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_cell_state")
    assert sensor.state == "Bypass"


async def test_cell_state_sensor_defrosting(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test cell state sensor in defrosting state."""
    # Arrange
    metrics = {"A_CYC_CELL_STATE": 3}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_cell_state")
    assert sensor.state == "Defrosting"


async def test_cell_state_sensor_unknown_state(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test cell state sensor in unknown state."""
    # Arrange
    metrics = {"A_CYC_CELL_STATE": 4}

    # Act
    with patch_metrics(metrics=metrics):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_cell_state")
    assert sensor.state == "unknown"
