"""Tests for Srp Energy component coordinator."""

from datetime import datetime as dt
from unittest.mock import MagicMock

from freezegun.api import freeze_time
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    statistics_during_period,
)
from homeassistant.components.srp_energy import SRPEnergyDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import PHOENIX_ZONE_INFO

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done


@freeze_time("2022-08-02T12:00:00-07:00")
async def test_coordinator_first_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_srp_energy: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator on its first run with no existing statistics.

    Should import multiple days of statistics.
    """
    coordinator = SRPEnergyDataUpdateCoordinator(
        hass, mock_config_entry, mock_srp_energy
    )

    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    # Check stats for electric account '123456789'
    stats = await get_stats(hass)
    assert stats == snapshot


async def test_coordinator_subsequent_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_srp_energy: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs."""
    coordinator = SRPEnergyDataUpdateCoordinator(
        hass, mock_config_entry, mock_srp_energy
    )

    mock_srp_energy.usage.side_effect = None
    mock_srp_energy.usage.return_value = [
        ("7/31/2022", "05:00 PM", "2022-07-31T17:00:00", 2.6, 0.37),
        ("7/31/2022", "06:00 PM", "2022-07-31T18:00:00", 4.5, 0.64),
        ("7/31/2022", "07:00 PM", "2022-07-31T19:00:00", 2.2, 0.32),
        ("7/31/2022", "08:00 PM", "2022-07-31T20:00:00", 0.0, 0.0),
        ("7/31/2022", "09:00 PM", "2022-07-31T21:00:00", 0.0, 0.0),
        ("7/31/2022", "10:00 PM", "2022-07-31T22:00:00", 0.0, 0.0),
        ("7/31/2022", "11:00 PM", "2022-07-31T23:00:00", 0.0, 0.0),
    ]

    # Run aug 2nd at midnight to import through aug 1
    # BUT tends to be missing last few hours
    with freeze_time("2022-08-02T00:00:00-07:00"):
        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

    stats = await get_stats(hass)
    last_consumption = stats["srp_energy:123456789_energy_consumption"][-1]
    assert_stat(last_consumption, "2022-07-31T19:00:00-07:00", 2.2, 9.3)
    last_cost = stats["srp_energy:123456789_energy_cost"][-1]
    assert_stat(last_cost, "2022-07-31T19:00:00-07:00", 0.32, 1.33)

    mock_srp_energy.usage.return_value = [
        ("7/31/2022", "05:00 PM", "2022-07-31T17:00:00", 2.6, 0.37),
        ("7/31/2022", "06:00 PM", "2022-07-31T18:00:00", 4.5, 0.64),
        ("7/31/2022", "07:00 PM", "2022-07-31T19:00:00", 2.5, 0.35),  # was 2.2 / 0.32
        ("7/31/2022", "08:00 PM", "2022-07-31T20:00:00", 2.9, 0.42),  # was 0 / 0
        ("7/31/2022", "09:00 PM", "2022-07-31T21:00:00", 2.2, 0.32),  # was 0 / 0
        ("7/31/2022", "10:00 PM", "2022-07-31T22:00:00", 2.1, 0.30),  # was 0 / 0
        ("7/31/2022", "11:00 PM", "2022-07-31T23:00:00", 2.0, 0.28),  # was 0 / 0
    ]
    # Run aug 2nd at 5am to get the updated data for aug 1
    with freeze_time("2022-08-02T05:00:00-07:00"):
        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

    stats = await get_stats(hass)
    last_consumption = stats["srp_energy:123456789_energy_consumption"][-1]
    assert_stat(last_consumption, "2022-07-31T23:00:00-07:00", 2.0, 18.8)
    last_cost = stats["srp_energy:123456789_energy_cost"][-1]
    assert_stat(last_cost, "2022-07-31T23:00:00-07:00", 0.28, 2.68)
    assert stats == snapshot


def assert_stat(
    stat: StatisticsRow, expected_start: str, expected_state: float, expected_sum: float
) -> None:
    """Helper function to assert a single statistics row."""
    assert (
        dt.fromtimestamp(stat["start"], PHOENIX_ZONE_INFO).isoformat() == expected_start
    )
    assert round(stat["state"], 2) == expected_state
    assert round(stat["sum"], 2) == expected_sum


async def test_coordinator_statistics_gap(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_srp_energy: MagicMock,
) -> None:
    """Test coordinator handles a gap between stored stats and SRP's available data.

    When SRP's 30-day API window rolls past the period covered by stored statistics,
    statistics_during_period finds nothing at hourly_usage[0].start_time. The else
    branch should fall back to the last known running sums and continue the totals
    from there rather than restarting from zero.
    """
    coordinator = SRPEnergyDataUpdateCoordinator(
        hass, mock_config_entry, mock_srp_energy
    )

    # First run: establish two stat entries so get_last_statistics returns 2 records.
    mock_srp_energy.usage.side_effect = None
    mock_srp_energy.usage.return_value = [
        ("7/31/2022", "05:00 PM", "2022-07-31T17:00:00", 2.0, 0.20),
        ("7/31/2022", "06:00 PM", "2022-07-31T18:00:00", 3.0, 0.30),
    ]

    with freeze_time("2022-08-01T12:00:00-07:00"):
        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

    stats = await get_stats(hass)
    assert_stat(
        stats["srp_energy:123456789_energy_consumption"][-1],
        "2022-07-31T18:00:00-07:00",
        3.0,
        5.0,
    )
    assert_stat(
        stats["srp_energy:123456789_energy_cost"][-1],
        "2022-07-31T18:00:00-07:00",
        0.30,
        0.50,
    )

    # Second run: SRP's API window has advanced so it only returns data starting
    # AFTER the most recent stored stat (18:00). statistics_during_period will find
    # nothing at 20:00 or later, triggering the else branch.
    mock_srp_energy.usage.return_value = [
        ("7/31/2022", "08:00 PM", "2022-07-31T20:00:00", 4.0, 0.40),
        ("7/31/2022", "09:00 PM", "2022-07-31T21:00:00", 5.0, 0.50),
    ]

    with freeze_time("2022-09-01T12:00:00-07:00"):
        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

    stats = await get_stats(hass)
    # Sums must continue from the last stored values (5.0 kWh / $0.50), not restart.
    assert_stat(
        stats["srp_energy:123456789_energy_consumption"][-2],
        "2022-07-31T20:00:00-07:00",
        4.0,
        9.0,
    )
    assert_stat(
        stats["srp_energy:123456789_energy_consumption"][-1],
        "2022-07-31T21:00:00-07:00",
        5.0,
        14.0,
    )
    assert_stat(
        stats["srp_energy:123456789_energy_cost"][-2],
        "2022-07-31T20:00:00-07:00",
        0.40,
        0.90,
    )
    assert_stat(
        stats["srp_energy:123456789_energy_cost"][-1],
        "2022-07-31T21:00:00-07:00",
        0.50,
        1.40,
    )


async def test_coordinator_subsequent_run_no_energy_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_srp_energy: MagicMock,
) -> None:
    """Test the coordinator handles no recent usage/cost data."""
    coordinator = SRPEnergyDataUpdateCoordinator(
        hass, mock_config_entry, mock_srp_energy
    )
    await coordinator._async_update_data()

    await async_wait_recording_done(hass)


async def get_stats(hass: HomeAssistant) -> dict[str, list[StatisticsRow]]:
    """Helper function to get the latest statistics."""
    return await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "srp_energy:123456789_energy_consumption",
            "srp_energy:123456789_energy_cost",
        },
        "hour",
        None,
        {"state", "sum"},
    )
