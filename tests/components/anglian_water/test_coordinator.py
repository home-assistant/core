"""Tests for the Anglian Water coordinator."""

from unittest.mock import AsyncMock

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
