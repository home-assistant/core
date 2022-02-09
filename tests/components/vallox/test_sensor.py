"""Tests for Vallox sensor platform."""

from datetime import datetime, timedelta, tzinfo

import pytest

from homeassistant.components.vallox.const import (
    METRIC_KEY_DAY,
    METRIC_KEY_HOUR,
    METRIC_KEY_MINUTE,
    METRIC_KEY_MONTH,
    METRIC_KEY_REMAINING_TIME_FOR_FILTER,
    METRIC_KEY_YEAR,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from .conftest import patch_ha_now, patch_metrics

from tests.common import MockConfigEntry, async_fire_time_changed

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


def _patch_vallox_now_and_remaining_days(remaining_days=10, now=dt.now()):
    return patch_metrics(
        {
            METRIC_KEY_REMAINING_TIME_FOR_FILTER: remaining_days,
            METRIC_KEY_YEAR: now.year - 2000,
            METRIC_KEY_MONTH: now.month,
            METRIC_KEY_DAY: now.day,
            METRIC_KEY_HOUR: now.hour,
            METRIC_KEY_MINUTE: now.minute,
        },
    )


def _patch_vallox_remaining_days(remaining_days=10):
    return patch_metrics(
        {METRIC_KEY_REMAINING_TIME_FOR_FILTER: remaining_days},
    )


def _sensor_to_date(sensor):
    sensor_state_datetime = datetime.fromisoformat(sensor.state)
    return sensor_state_datetime.date()


async def test_remaining_filter_returns_timestamp(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test that the remaining time for filter sensor returns a timestamp."""
    # Act
    with _patch_vallox_now_and_remaining_days():
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert sensor.attributes["device_class"] == "timestamp"


async def test_remaining_filter_no_vallox_datetime(
    mock_entry: MockConfigEntry, hass: HomeAssistant
):
    """Test that the remaining time for filter works if Vallox doesn't return any time."""
    # Arrange
    remaining_days = 8
    now = dt.now()
    expected_filter_end_date = now.date() + timedelta(days=remaining_days)

    # Act
    with _patch_vallox_remaining_days(remaining_days=remaining_days):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_clocks_in_sync_more_than_one_minute_before_midnight(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Test remaining time for filter with clocks in sync and the time is close to midnight."""
    # Arrange
    remaining_days = 18
    now = dt.now().replace(hour=23, minute=58, second=47)
    expected_filter_end_date = now.date() + timedelta(days=remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=remaining_days, now=now
    ), patch_ha_now(now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_clocks_in_sync_less_than_one_minute_before_midnight(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks in sync and the time is less than one minute before midnight."""
    # Arrange
    remaining_days = 20
    now = dt.now().replace(hour=23, minute=59, second=12)
    expected_filter_end_date = now.date() + timedelta(days=remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=remaining_days, now=now
    ), patch_ha_now(now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_clocks_in_sync_less_than_one_minute_after_midnight(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks in sync and the time is less than one minute after midnight."""
    # Arrange
    remaining_days = 20
    now = dt.now().replace(hour=0, minute=0, second=24)
    expected_filter_end_date = now.date() + timedelta(days=remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=remaining_days, now=now
    ), patch_ha_now(now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_clocks_in_sync_more_than_one_minute_after_midnight(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks in sync and the time is more than one minute after midnight."""
    # Arrange
    remaining_days = 20
    now = dt.now().replace(hour=0, minute=1, second=33)
    expected_filter_end_date = now.date() + timedelta(days=remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=remaining_days, now=now
    ), patch_ha_now(now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_vallox_clock_three_minutes_before_ha(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks out of sync and Vallox being before midnight and HA after midnight."""
    # Arrange
    actual_remaining_days = 74
    vallox_remaining_days = actual_remaining_days + 1
    ha_now = dt.now().replace(hour=0, minute=1, second=54)
    vallox_now = ha_now - timedelta(minutes=3)
    expected_filter_end_date = ha_now.date() + timedelta(days=actual_remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=vallox_remaining_days, now=vallox_now
    ), patch_ha_now(ha_now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_vallox_clock_four_minutes_after_ha(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks out of sync and Vallox being after midnight and HA before midnight."""
    # Arrange
    actual_remaining_days = 65
    vallox_remaining_days = actual_remaining_days - 1
    ha_now = dt.now().replace(hour=23, minute=58, second=22)
    vallox_now = ha_now + timedelta(minutes=4)
    expected_filter_end_date = ha_now.date() + timedelta(days=actual_remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=vallox_remaining_days, now=vallox_now
    ), patch_ha_now(ha_now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_vallox_clock_two_hours_before_ha(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks out of sync and both being before midnight."""
    # Arrange
    remaining_days = 91
    ha_now = dt.now().replace(hour=23, minute=58, second=22)
    vallox_now = ha_now - timedelta(hours=2)
    expected_filter_end_date = ha_now.date() + timedelta(days=remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=remaining_days, now=vallox_now
    ), patch_ha_now(ha_now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_vallox_clock_two_hours_after_ha(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks out of sync and Vallox being after midnight and HA before midnight."""
    # Arrange
    actual_remaining_days = 82
    vallox_remaining_days = actual_remaining_days - 1
    ha_now = dt.now().replace(hour=23, minute=58, second=22)
    vallox_now = ha_now + timedelta(hours=2)
    expected_filter_end_date = ha_now.date() + timedelta(days=actual_remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=vallox_remaining_days, now=vallox_now
    ), patch_ha_now(ha_now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_vallox_clock_two_days_one_hour_before_ha(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks much out of sync and Vallox being more than 2 days before HA."""
    # Arrange
    actual_remaining_days = 34
    vallox_remaining_days = actual_remaining_days + 2
    ha_now = dt.now().replace(hour=23, minute=58, second=22)
    vallox_now = ha_now - timedelta(days=2, hours=1)
    expected_filter_end_date = ha_now.date() + timedelta(days=actual_remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=vallox_remaining_days, now=vallox_now
    ), patch_ha_now(ha_now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_vallox_clock_two_days_one_hour_after_ha(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
):
    """Clocks much out of sync and Vallox being more than 2 days after HA."""
    # Arrange
    actual_remaining_days = 11
    vallox_remaining_days = actual_remaining_days - 3
    ha_now = dt.now().replace(hour=23, minute=58, second=22)
    vallox_now = ha_now + timedelta(days=2, hours=1)
    expected_filter_end_date = ha_now.date() + timedelta(days=actual_remaining_days)

    # Act
    with _patch_vallox_now_and_remaining_days(
        remaining_days=vallox_remaining_days, now=vallox_now
    ), patch_ha_now(ha_now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Assert
    sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
    assert _sensor_to_date(sensor) == expected_filter_end_date


@pytest.mark.parametrize(
    "set_tz",
    [
        "utc",
        "helsinki",
        "new_york",
    ],
    indirect=True,
)
async def test_remaining_filter_time_clocks_in_sync_full_day(
    mock_entry: MockConfigEntry, set_tz: tzinfo, hass: HomeAssistant
) -> None:
    """Test the remaining filter time sensor for more than one full day."""
    # Arrange
    remaining_days = 132
    now = dt.now()
    start_day = now.day
    expected_filter_end_date = now.date() + timedelta(days=remaining_days)

    with _patch_vallox_now_and_remaining_days(remaining_days=remaining_days, now=now):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Act & Assert
    for hour in range(0, 27):
        for minute in (0, 30):
            new_now = now + timedelta(hours=hour, minutes=minute)
            if new_now.day != start_day:
                start_day = new_now.day
                remaining_days -= 1

            with _patch_vallox_now_and_remaining_days(
                remaining_days=remaining_days, now=new_now
            ), patch_ha_now(
                new_now,
            ):
                async_fire_time_changed(hass, datetime_=new_now)
                await hass.async_block_till_done()

            sensor = hass.states.get("sensor.vallox_remaining_time_for_filter")
            assert _sensor_to_date(sensor) == expected_filter_end_date
