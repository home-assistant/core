"""Tests for WaterFurnace energy statistics."""

from datetime import datetime, timedelta
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from waterfurnace.waterfurnace import WFCredentialError, WFEnergyData

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    statistics_during_period,
)
from homeassistant.components.waterfurnace.const import DOMAIN, ENERGY_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done

STATISTIC_ID = f"{DOMAIN}:test_gwid_12345_energy"

# All time-sensitive tests are pinned to this instant.
NOW = "2025-01-15 12:00:00+00:00"
_NOW_DT = dt_util.as_utc(dt_util.parse_datetime(NOW))


def _make_energy_data(readings: list[tuple[datetime, float]]) -> WFEnergyData:
    """Build a WFEnergyData from (timestamp, total_power_kwh) pairs."""
    columns = ["total_power"]
    index = [int(ts.timestamp() * 1000) for ts, _ in readings]
    data = [[kwh] for _, kwh in readings]
    return WFEnergyData({"columns": columns, "index": index, "data": data})


async def _get_stats(
    hass: HomeAssistant,
    start: datetime,
    end: datetime,
) -> list[StatisticsRow]:
    """Get statistics for the test statistic_id."""
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        start,
        end,
        {STATISTIC_ID},
        "hour",
        None,
        {"state", "sum"},
    )
    return stats.get(STATISTIC_ID, [])


async def _trigger_energy_poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance time to trigger an energy poll."""
    freezer.tick(ENERGY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # The coordinator reads from the recorder on an executor thread, then
    # calls async_add_external_statistics which queues a write back to the
    # recorder thread. A single flush isn't enough because the write is
    # queued after the event loop task completes. Flush twice to ensure the
    # full event-loop → recorder → event-loop → recorder chain settles.
    await async_wait_recording_done(hass)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)


@pytest.mark.freeze_time(NOW)
async def test_poll_inserts_statistics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that energy data is fetched and inserted as statistics."""
    t1 = _NOW_DT - timedelta(hours=2)
    t2 = _NOW_DT - timedelta(hours=1)

    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t1, 2.0), (t2, 3.0)]
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    entries = await _get_stats(hass, t1, t2 + timedelta(seconds=1))
    assert len(entries) == 2
    assert entries[0]["state"] == pytest.approx(2.0)
    assert entries[0]["sum"] == pytest.approx(2.0)
    assert entries[1]["state"] == pytest.approx(3.0)
    assert entries[1]["sum"] == pytest.approx(5.0)


@pytest.mark.freeze_time(NOW)
async def test_poll_skips_current_hour(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that readings from the current incomplete hour are skipped."""
    t_completed = _NOW_DT - timedelta(hours=1)
    t_current = _NOW_DT

    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t_completed, 2.0), (t_current, 5.0)]
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    entries = await _get_stats(hass, t_completed, t_current + timedelta(seconds=1))
    assert len(entries) == 1
    assert entries[0]["sum"] == pytest.approx(2.0)


async def test_poll_empty_response(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that empty energy data response is handled gracefully."""
    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data([])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.freeze_time(NOW)
async def test_subsequent_poll_resumes_sum(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that subsequent polls correctly resume from the last recorded sum."""
    t1 = _NOW_DT - timedelta(hours=1)

    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t1, 4.0)]
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # Advance time so t2 becomes a completed hour, then poll again
    t2 = _NOW_DT
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t2, 6.0)]
    )
    await _trigger_energy_poll(hass, freezer)

    entries = await _get_stats(hass, t2, t2 + timedelta(seconds=1))
    assert len(entries) == 1
    assert entries[0]["state"] == pytest.approx(6.0)
    assert entries[0]["sum"] == pytest.approx(10.0)


async def test_no_data_error_handled_gracefully(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that WFNoDataError does not prevent integration setup."""
    # Default conftest sets get_energy_data.side_effect = WFNoDataError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.freeze_time(NOW)
async def test_login_credential_error_raises_update_failed(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that WFCredentialError during energy login raises UpdateFailed."""
    # First setup succeeds with no data
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # On next poll, login fails with credential error
    mock_waterfurnace_client.login.side_effect = WFCredentialError("bad creds")
    mock_waterfurnace_client.get_energy_data.side_effect = None

    await _trigger_energy_poll(hass, freezer)

    device_data = mock_config_entry.runtime_data["TEST_GWID_12345"]
    assert device_data.energy.last_update_success is False


@pytest.mark.freeze_time(NOW)
async def test_timezone_conversion(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that energy data is correctly handled across time zones."""
    await hass.config.async_set_time_zone("America/New_York")

    t1 = _NOW_DT - timedelta(hours=2)
    t2 = _NOW_DT - timedelta(hours=1)

    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t1, 1.5), (t2, 2.5)]
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    entries = await _get_stats(hass, t1, t2 + timedelta(seconds=1))
    assert len(entries) == 2
    assert entries[0]["sum"] == pytest.approx(1.5)
    assert entries[1]["sum"] == pytest.approx(4.0)

    # Verify the API was called with dates in the configured timezone
    call_args = mock_waterfurnace_client.get_energy_data.call_args
    assert call_args.kwargs.get("timezone_str") == "America/New_York"
