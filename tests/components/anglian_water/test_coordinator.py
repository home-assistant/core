"""Tests for the Anglian Water coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from pyanglianwater.meter import SmartMeter
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.anglian_water.coordinator import (
    AnglianWaterUpdateCoordinator,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import (
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import ACCOUNT_NUMBER

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done


async def test_coordinator_first_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator on its first run with no existing statistics."""
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

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


async def test_coordinator_subsequent_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    mock_anglian_water_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs."""
    # 1st run
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # 2nd run with an updated reading for one read and a new read added.
    mock_smart_meter.readings[-1] = {
        "read_at": "2024-06-01T14:00:00Z",
        "consumption": 35,
        "read": 70,
    }
    mock_smart_meter.readings.append(
        {"read_at": "2024-06-01T15:00:00Z", "consumption": 20, "read": 90}
    )
    await coordinator._async_update_data()
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


async def test_coordinator_subsequent_run_no_energy_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    mock_anglian_water_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles no recent usage/cost data."""
    # 1st run
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # 2nd run with no readings
    mock_smart_meter.readings = []
    await coordinator._async_update_data()

    assert "No recent usage statistics found, skipping update" in caplog.text
    # Verify no new stats were added by checking the sum remains 50
    statistic_id = f"anglian_water:{ACCOUNT_NUMBER}_testsn_usage"
    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert stats[statistic_id][0]["sum"] == 50


async def test_coordinator_invalid_readings(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    mock_anglian_water_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles bad data / invalid readings correctly."""
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Test that an invalid read_at on the first reading skips the entire update
    mock_smart_meter.readings = [
        {"read_at": "invalid-date-format", "consumption": 10, "read": 10},
    ]
    await coordinator._async_update_data()

    assert (
        "Could not parse read_at time invalid-date-format, skipping update"
        in caplog.text
    )

    # Test that individual invalid readings are skipped
    mock_smart_meter.readings = [
        {"read_at": "2024-06-01T12:00:00Z", "consumption": 10, "read": 10},
        {"read_at": "also-invalid-date", "consumption": 15, "read": 25},
    ]
    await coordinator._async_update_data()

    assert (
        "Could not parse read_at time also-invalid-date, skipping reading"
        in caplog.text
    )


async def test_coordinator_subsequent_run_missing_period_statistics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    mock_anglian_water_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles missing period lookup statistics."""
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
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
        await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    assert "Could not find existing statistics during period lookup" in caplog.text

    statistic_id = f"anglian_water:{ACCOUNT_NUMBER}_testsn_usage"
    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert stats[statistic_id][0]["sum"] >= 70

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


async def test_coordinator_cost_statistics_first_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test cost statistics distribute the day's cost by consumption share."""
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    statistic_id = f"anglian_water:{ACCOUNT_NUMBER}_testsn_cost"
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
    rows = stats[statistic_id]
    # £1.00 for the day, split across 10L/15L/25L readings
    assert [round(row["state"], 2) for row in rows] == [0.2, 0.3, 0.5]
    assert round(rows[-1]["sum"], 2) == 1.0


async def test_coordinator_cost_statistics_subsequent_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test cost statistics only append hours newer than the last stored one."""
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # A new reading arrives for the same day.
    mock_smart_meter.readings.append(
        {"read_at": "2024-06-01T15:00:00", "consumption": 50, "read": 100}
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    statistic_id = f"anglian_water:{ACCOUNT_NUMBER}_testsn_cost"
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
    rows = stats[statistic_id]
    assert len(rows) == 4
    # The new hour is 50L of the day's (now) 100L -> £0.50, appended to the sum
    assert round(rows[-1]["state"], 2) == 0.5
    assert round(rows[-1]["sum"], 2) == 1.5


async def test_coordinator_no_cost_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smart_meter: SmartMeter,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test that no cost statistics are inserted when no cost data exists."""
    mock_smart_meter.daily_costs = {}
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    statistic_id = f"anglian_water:{ACCOUNT_NUMBER}_testsn_cost"
    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert not stats


async def test_coordinator_period_statistics_without_sum(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test period lookup records without sum are handled safely."""
    coordinator = AnglianWaterUpdateCoordinator(
        hass, mock_anglian_water_client, mock_config_entry
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    statistic_id = f"anglian_water:{ACCOUNT_NUMBER}_testsn_usage"
    with patch(
        "homeassistant.components.anglian_water.coordinator.statistics_during_period",
        return_value={statistic_id: [{"start": 0.0}]},
    ):
        await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert stats[statistic_id]
