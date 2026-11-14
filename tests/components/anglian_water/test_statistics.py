"""Test Anglian Water statistics."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyanglianwater.meter import SmartMeter
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.recorder.common import async_wait_recording_done
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder.statistics import (
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import ACCOUNT_NUMBER


@pytest.mark.parametrize(
    ("readings"),
    [
        pytest.param([], id="no_new_readings"),
        pytest.param(
            [
                {
                    "read_at": "2024-06-01T14:00:00",
                    "consumption": 35,
                    "read": 70,
                },
                {
                    "read_at": "2024-06-01T15:00:00",
                    "consumption": 20,
                    "read": 90,
                },
            ],
            id="new_and_updated_readings",
        ),
        pytest.param(
            [
                {
                    "read_at": "2024-06-01T15:00:00",
                    "consumption": 20,
                    "read": 70,
                },
            ],
            id="new_readings_only",
        ),
        pytest.param(
            [
                {
                    "read_at": "2024-06-01T13:00:00",
                    "consumption": 20,
                    "read": 40,
                    "corrected": False,
                },
                {
                    "read_at": "2024-06-01T14:00:00",
                    "consumption": 35,
                    "read": 70,
                    "corrected": True,
                },
            ],
            id="corrected_reading",
        ),
    ],
)
@pytest.mark.usefixtures("recorder_mock", "mock_anglian_water_client")
async def test_statistics_subsequent_run(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    readings: list[dict[str, str | int]],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs."""
    # 1st run
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)

    # 2nd run
    mock_smart_meter.readings = readings
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)

    # Check all stats
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            f"anglian_water:{ACCOUNT_NUMBER}_testsn_usage",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == snapshot


@pytest.mark.parametrize(
    ("readings", "expected_log"),
    [
        pytest.param(
            [
                {
                    "read_at": "invalid-date-format",
                    "consumption": 10,
                    "read": 10,
                },
            ],
            "Could not parse read_at time invalid-date-format, skipping update",
            id="invalid_first_timestamp",
        ),
        pytest.param(
            [
                {
                    "read_at": "2024-06-01T12:00:00Z",
                    "consumption": 10,
                    "read": 10,
                },
                {
                    "read_at": "also-invalid-date",
                    "consumption": 15,
                    "read": 25,
                },
            ],
            "Could not parse read_at time also-invalid-date, skipping reading",
            id="invalid_later_timestamp",
        ),
        pytest.param(
            [],
            "No recent usage statistics found, skipping update",
            id="no_readings",
        ),
    ],
)
@pytest.mark.usefixtures("recorder_mock", "mock_anglian_water_client")
async def test_statistics_invalid_readings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    readings: list[dict[str, str | int]],
    expected_log: str,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test invalid timestamps are skipped without changing stored statistics."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)

    mock_smart_meter.readings = readings

    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)

    assert expected_log in caplog.text

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {f"anglian_water:{ACCOUNT_NUMBER}_testsn_usage"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == snapshot


@pytest.mark.usefixtures("recorder_mock", "mock_anglian_water_client")
async def test_statistics_missing_recorder_lookup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles missing period lookup statistics."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)

    # Correct the latest already-stored reading. Fallback should still update
    # this hour instead of skipping it.
    mock_smart_meter.readings[-1] = {
        "read_at": "2024-06-01T14:00:00",
        "consumption": 35,
        "read": 70,
    }

    # Add a new later reading to ensure fallback also accepts newer entries.
    mock_smart_meter.readings.append(
        {"read_at": "2024-06-01T15:00:00", "consumption": 20, "read": 90}
    )

    with patch(
        "homeassistant.components.anglian_water.coordinator.statistics_during_period",
        return_value={},
    ):
        freezer.tick(timedelta(hours=1, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        await async_wait_recording_done(hass)

    assert "Could not find existing statistics during period lookup" in caplog.text

    statistic_id = f"anglian_water:{ACCOUNT_NUMBER}_testsn_usage"
    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert stats[statistic_id][0]["sum"] == 90

    parsed_read_at = dt_util.parse_datetime("2024-06-01T14:00:00")
    assert parsed_read_at is not None
    corrected_start = dt_util.as_local(parsed_read_at) - timedelta(hours=1)

    corrected_stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        corrected_start,
        corrected_start + timedelta(seconds=1),
        {
            statistic_id,
        },
        "hour",
        None,
        {"sum"},
    )
    assert corrected_stats[statistic_id][0]["sum"] == 70


@pytest.mark.usefixtures("recorder_mock", "mock_anglian_water_client")
async def test_period_statistics_without_sum(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test period lookup records without sum are handled safely."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)

    statistic_id = f"anglian_water:{ACCOUNT_NUMBER}_testsn_usage"
    mock_smart_meter.readings.append(
        {"read_at": "2024-06-01T15:00:00", "consumption": 20, "read": 70}
    )
    with patch(
        "homeassistant.components.anglian_water.coordinator.statistics_during_period",
        return_value={statistic_id: [{"start": 0.0}]},
    ):
        freezer.tick(timedelta(hours=1, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {statistic_id},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == snapshot
