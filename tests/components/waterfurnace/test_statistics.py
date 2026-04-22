"""Tests for WaterFurnace energy statistics."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from waterfurnace.waterfurnace import WFCredentialError, WFEnergyData, WFNoDataError

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.models.statistics import StatisticData
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.components.waterfurnace.const import DOMAIN, ENERGY_UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import SEED_STATISTIC_METADATA

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


async def _get_last_stat(hass: HomeAssistant) -> StatisticsRow | None:
    """Get the most recent statistic."""
    last = await hass.async_add_executor_job(
        get_last_statistics, hass, 1, STATISTIC_ID, True, {"sum"}
    )
    rows = last.get(STATISTIC_ID)
    if not rows:
        return None
    return rows[0]


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


async def _setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the integration and wait for background tasks to settle."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.waterfurnace.coordinator.BACKFILL_DELAY_MIN_SECONDS",
            0,
        ),
        patch(
            "homeassistant.components.waterfurnace.coordinator.BACKFILL_DELAY_MAX_SECONDS",
            0,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        for device_data in mock_config_entry.runtime_data.values():
            if device_data.energy:
                await device_data.energy.async_wait_backfill()
    await async_wait_recording_done(hass)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)


# ---------------------------------------------------------------------------
# Normal poll tests (seed_statistics fixture ensures no backfill is triggered)
# ---------------------------------------------------------------------------


@pytest.mark.freeze_time(NOW)
@pytest.mark.usefixtures("seed_statistics")
async def test_poll_inserts_statistics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that energy data is fetched and inserted as statistics."""
    t1 = _NOW_DT - timedelta(hours=1)
    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t1, 3.0)]
    )

    await _setup_integration(hass, mock_config_entry)

    entries = await _get_stats(hass, t1, t1 + timedelta(seconds=1))
    assert len(entries) == 1
    assert entries[0]["state"] == pytest.approx(3.0)
    assert entries[0]["sum"] == pytest.approx(3.0)


@pytest.mark.freeze_time(NOW)
@pytest.mark.usefixtures("seed_statistics")
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

    await _setup_integration(hass, mock_config_entry)

    entries = await _get_stats(hass, t_completed, t_current + timedelta(seconds=1))
    assert len(entries) == 1
    assert entries[0]["sum"] == pytest.approx(2.0)


@pytest.mark.usefixtures("seed_statistics")
async def test_poll_empty_response(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that empty energy data response is handled gracefully."""
    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data([])

    await _setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.freeze_time(NOW)
@pytest.mark.usefixtures("seed_statistics")
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

    await _setup_integration(hass, mock_config_entry)

    # Advance time so t2 becomes available, then poll again
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
    await _setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.freeze_time(NOW)
@pytest.mark.usefixtures("seed_statistics")
async def test_login_credential_error_raises_update_failed(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that WFCredentialError during energy login raises UpdateFailed."""
    await _setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # On next poll, get_energy_data fails with expired session, then
    # re-login also fails with credential error.
    mock_waterfurnace_client.get_energy_data.side_effect = WFCredentialError(
        "session expired"
    )
    mock_waterfurnace_client.login.side_effect = WFCredentialError("bad creds")

    await _trigger_energy_poll(hass, freezer)

    device_data = mock_config_entry.runtime_data["TEST_GWID_12345"]
    assert device_data.energy.last_update_success is False


@pytest.mark.freeze_time(NOW)
@pytest.mark.usefixtures("seed_statistics")
async def test_timezone_conversion(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that energy data is correctly handled across time zones."""
    await hass.config.async_set_time_zone("America/New_York")

    t1 = _NOW_DT - timedelta(hours=1)
    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t1, 1.5)]
    )

    await _setup_integration(hass, mock_config_entry)

    entries = await _get_stats(hass, t1, t1 + timedelta(seconds=1))
    assert len(entries) == 1
    assert entries[0]["sum"] == pytest.approx(1.5)

    # Verify the API was called with dates in the configured timezone
    call_args = mock_waterfurnace_client.get_energy_data.call_args
    assert call_args.kwargs.get("timezone_str") == "America/New_York"


# ---------------------------------------------------------------------------
# Backfill tests (no seed_statistics — these intentionally trigger backfill)
# ---------------------------------------------------------------------------


@pytest.mark.freeze_time(NOW)
async def test_first_poll_no_statistics_triggers_reverse_backfill(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test first poll with no existing statistics triggers reverse backfill."""
    t1 = _NOW_DT - timedelta(hours=2)

    def side_effect(start: str, end: str, **kwargs: str) -> WFEnergyData:
        if start <= t1.strftime("%Y-%m-%d") <= end:
            return _make_energy_data([(t1, 5.0)])
        raise WFNoDataError("No data")

    mock_waterfurnace_client.get_energy_data.side_effect = side_effect

    await _setup_integration(hass, mock_config_entry)

    last = await _get_last_stat(hass)
    assert last is not None
    assert last["sum"] == pytest.approx(5.0)


@pytest.mark.freeze_time(NOW)
async def test_gap_backfill(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test gap backfill when last stat is older than gap threshold."""
    t0 = _NOW_DT - timedelta(days=7)
    async_add_external_statistics(
        hass,
        SEED_STATISTIC_METADATA,
        [StatisticData(start=t0, state=1.0, sum=10.0)],
    )
    await async_wait_recording_done(hass)

    t1 = _NOW_DT - timedelta(days=5)
    t2 = _NOW_DT - timedelta(days=1)
    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t1, 2.0), (t2, 3.0)]
    )

    await _setup_integration(hass, mock_config_entry)

    last = await _get_last_stat(hass)
    assert last is not None
    assert last["sum"] == pytest.approx(15.0)


@pytest.mark.freeze_time(NOW)
async def test_reverse_backfill_stops_on_no_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that WFNoDataError during reverse backfill skips gaps."""
    t1 = _NOW_DT - timedelta(hours=2)

    def side_effect(start: str, end: str, **kwargs: str) -> WFEnergyData:
        if start <= t1.strftime("%Y-%m-%d") <= end:
            return _make_energy_data([(t1, 7.0)])
        raise WFNoDataError("No data")

    mock_waterfurnace_client.get_energy_data.side_effect = side_effect

    await _setup_integration(hass, mock_config_entry)

    # Reverse backfill continues past WFNoDataError gaps, so it should
    # have made more calls than just the one successful batch.
    assert mock_waterfurnace_client.get_energy_data.call_count > 2

    last = await _get_last_stat(hass)
    assert last is not None
    assert last["sum"] == pytest.approx(7.0)


@pytest.mark.freeze_time(NOW)
async def test_reverse_backfill_early_stop_on_consecutive_empty(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that reverse backfill stops after BACKFILL_MAX_EMPTY_DAYS with no data."""
    mock_waterfurnace_client.get_energy_data.side_effect = WFNoDataError("No data")

    await _setup_integration(hass, mock_config_entry)

    # 15 empty days / 5-day batches = 3 batches before early stop,
    # not the full 79 batches for 395 days.
    assert mock_waterfurnace_client.get_energy_data.call_count == 3


@pytest.mark.freeze_time(NOW)
async def test_backfill_then_normal_poll(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that backfill followed by normal poll produces correct cumulative sums."""
    t0 = _NOW_DT - timedelta(days=6)
    async_add_external_statistics(
        hass,
        SEED_STATISTIC_METADATA,
        [StatisticData(start=t0, state=1.0, sum=100.0)],
    )
    await async_wait_recording_done(hass)

    t1 = _NOW_DT - timedelta(days=4)
    t2 = _NOW_DT - timedelta(days=1)
    mock_waterfurnace_client.get_energy_data.side_effect = None
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t1, 2.0), (t2, 3.0)]
    )

    await _setup_integration(hass, mock_config_entry)

    # Now do a normal poll (last stat is now recent)
    t3 = _NOW_DT
    mock_waterfurnace_client.get_energy_data.return_value = _make_energy_data(
        [(t3, 4.0)]
    )
    await _trigger_energy_poll(hass, freezer)

    last = await _get_last_stat(hass)
    assert last is not None
    assert last["sum"] == pytest.approx(109.0)


@pytest.mark.freeze_time(NOW)
async def test_backfill_multi_batch_running_totals(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test multi-day backfill produces correct running totals across batches."""
    t0 = _NOW_DT - timedelta(days=8)
    async_add_external_statistics(
        hass,
        SEED_STATISTIC_METADATA,
        [StatisticData(start=t0, state=0.0, sum=50.0)],
    )
    await async_wait_recording_done(hass)

    t1 = _NOW_DT - timedelta(days=6)
    t2 = _NOW_DT - timedelta(days=3)
    t3 = _NOW_DT - timedelta(days=1)

    def side_effect(start: str, end: str, **kwargs: str) -> WFEnergyData:
        results = []
        for t, kwh in ((t1, 10.0), (t2, 20.0), (t3, 30.0)):
            if start <= t.strftime("%Y-%m-%d") < end:
                results.append((t, kwh))
        return _make_energy_data(results)

    mock_waterfurnace_client.get_energy_data.side_effect = side_effect

    await _setup_integration(hass, mock_config_entry)

    last = await _get_last_stat(hass)
    assert last is not None
    assert last["sum"] == pytest.approx(110.0)
