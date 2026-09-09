"""Tests for Tesla Fleet historical energy statistics."""

from asyncio import Event, wait_for
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, call, patch

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.const import TeslaEnergyPeriod
from tesla_fleet_api.exceptions import (
    InvalidToken,
    LoginRequired,
    OAuthExpired,
    RateLimited,
    TeslaFleetError,
)

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    statistics_during_period,
)
from homeassistant.components.tesla_fleet.coordinator import (
    ENERGY_HISTORY_INTERVAL,
    TeslaFleetEnergySiteHistoryCoordinator,
)
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import setup_platform
from .conftest import UID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done

SITE_ID = "123456"
SITE_NAME = "Energy Site"
SITE_TIME_ZONE = "America/Los_Angeles"
GRID = "grid_energy_imported"
SOLAR = "solar_energy_exported"
GRID_STATISTIC_ID = f"tesla_fleet:{SITE_ID}_{GRID}"
SOLAR_STATISTIC_ID = f"tesla_fleet:{SITE_ID}_{SOLAR}"
BEFORE = "2023-06-01T23:45:00-07:00"
LAST = "2023-06-01T23:55:00-07:00"
AFTER = "2023-06-02T00:05:00-07:00"
END_DATE = "2023-06-01T23:59:59-07:00"


def _history(
    *samples: tuple[str | None, dict[str, float]],
    time_zone: str | None = SITE_TIME_ZONE,
) -> dict[str, Any]:
    """Build a response without repeating the API envelope in each case."""
    return {
        "response": {
            "period": "day",
            "installation_time_zone": time_zone,
            "time_series": [
                {"timestamp": timestamp, **values} for timestamp, values in samples
            ],
        }
    }


async def _refresh(
    hass: HomeAssistant, coordinator: TeslaFleetEnergySiteHistoryCoordinator
) -> dict[str, Any]:
    """Refresh sensors and finish the background import and recorder writes."""
    output = await coordinator._async_update_data()
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)
    return output


async def _get_hourly_stats(
    hass: HomeAssistant, statistic_ids: set[str]
) -> dict[str, list[StatisticsRow]]:
    """Read the imported hourly statistics."""
    return await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        statistic_ids,
        "hour",
        None,
        {"state", "sum"},
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a config entry for the coordinator."""
    return MockConfigEntry(domain="tesla_fleet", title=UID, unique_id=UID, data={})


@pytest.fixture
def mock_energy_site() -> AsyncMock:
    """Mock the energy site's API."""
    api = AsyncMock()
    api.energy_site_id = SITE_ID
    api.energy_history.return_value = _history((BEFORE, {GRID: 100}))
    return api


@pytest.fixture
def coordinator(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> TeslaFleetEnergySiteHistoryCoordinator:
    """Create a coordinator with an isolated recorder."""
    mock_config_entry.add_to_hass(hass)
    return TeslaFleetEnergySiteHistoryCoordinator(
        hass, mock_config_entry, mock_energy_site, SITE_NAME
    )


@pytest.fixture
def history_responses(
    mock_energy_site: AsyncMock,
) -> dict[str | None, dict[str, Any]]:
    """Serve daily responses keyed by their requested end date."""
    responses: dict[str | None, dict[str, Any]] = {}

    def get_history(
        period: TeslaEnergyPeriod, *, end_date: str | None = None
    ) -> dict[str, Any]:
        assert period is TeslaEnergyPeriod.DAY
        return deepcopy(responses[end_date])

    mock_energy_site.energy_history.side_effect = get_history
    return responses


async def test_coordinator_first_run(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Initialize from today's readings without requesting older history."""
    mock_energy_site.energy_history.return_value = _history(
        (
            "2023-06-01T08:00:00-07:00",
            {SOLAR: 1000, GRID: 500, "battery_energy_exported": 200},
        ),
        (
            "2023-06-01T09:00:00-07:00",
            {SOLAR: 1500, GRID: 300, "battery_energy_exported": 100},
        ),
    )
    await _refresh(hass, coordinator)
    mock_energy_site.energy_history.assert_called_once_with(TeslaEnergyPeriod.DAY)
    assert (
        await _get_hourly_stats(
            hass,
            {
                GRID_STATISTIC_ID,
                SOLAR_STATISTIC_ID,
                f"tesla_fleet:{SITE_ID}_battery_energy_exported",
            },
        )
        == snapshot
    )


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({}, id="missing-response"),
        pytest.param(_history(), id="empty-series"),
        pytest.param(_history((None, {GRID: 100})), id="missing-timestamp"),
    ],
)
async def test_invalid_current_data(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
    response: dict[str, Any],
) -> None:
    """Invalid current-day data still fails the sensor refresh."""
    mock_energy_site.energy_history.return_value = response
    with pytest.raises(UpdateFailed):
        await _refresh(hass, coordinator)


async def test_hourly_aggregation_and_repeated_refresh(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
) -> None:
    """Merge duplicate instants, skip untimed samples, and replace the latest hour."""
    mock_energy_site.energy_history.return_value = _history(
        ("2023-06-01T08:12:34-07:00", {GRID: 100, SOLAR: 200}),
        ("2023-06-01T15:12:34Z", {GRID: 150}),
        ("2023-06-01T08:45:00-07:00", {GRID: 50}),
        (None, {GRID: 1000}),
    )
    output = await _refresh(hass, coordinator)
    assert output[GRID] == 1300
    ids = {GRID_STATISTIC_ID, SOLAR_STATISTIC_ID}
    stats = await _get_hourly_stats(hass, ids)
    assert stats[GRID_STATISTIC_ID][0]["state"] == 200
    assert (
        stats[GRID_STATISTIC_ID][0]["start"]
        == datetime.fromisoformat("2023-06-01T15:00:00+00:00").timestamp()
    )
    assert stats[SOLAR_STATISTIC_ID][0]["sum"] == 200

    mock_energy_site.energy_history.return_value["response"]["time_series"].extend(
        [
            {"timestamp": "2023-06-01T08:55:00-07:00", GRID: 25},
            {"timestamp": "2023-06-01T09:00:00-07:00", GRID: 75},
        ]
    )
    await _refresh(hass, coordinator)
    stats = await _get_hourly_stats(hass, ids)
    assert [row["state"] for row in stats[GRID_STATISTIC_ID]] == [225, 75]
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 300
    await _refresh(hass, coordinator)
    assert await _get_hourly_stats(hass, ids) == stats


@pytest.mark.parametrize(
    ("time_zone", "date", "expected_states"),
    [
        pytest.param(SITE_TIME_ZONE, "2023-06-01", [10, 170, 45], id="pacific"),
        pytest.param("Asia/Kolkata", "2023-06-01", [10, 215], id="half-hour"),
        pytest.param("Pacific/Chatham", "2023-06-01", [10, 215], id="quarter-hour"),
        pytest.param(SITE_TIME_ZONE, "2023-03-12", [10, 170, 45], id="spring-dst"),
        pytest.param(SITE_TIME_ZONE, "2023-11-05", [10, 170, 45], id="fall-dst"),
    ],
)
async def test_backfill_after_midnight(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
    history_responses: dict[str | None, dict[str, Any]],
    time_zone: str,
    date: str,
    expected_states: list[float],
) -> None:
    """Restore the old day's tail and whole UTC buckets after a restart."""
    zone = await dt_util.async_get_time_zone(time_zone)
    assert zone is not None
    day = datetime.fromisoformat(date).replace(tzinfo=zone)
    tomorrow = day + timedelta(days=1)
    before = [
        ((day + timedelta(hours=22)).isoformat(), {GRID: 10}),
        ((day + timedelta(hours=23, minutes=45)).isoformat(), {GRID: 100}),
    ]
    history_responses[None] = _history(*before, time_zone=time_zone)
    await _refresh(hass, coordinator)
    coordinator = TeslaFleetEnergySiteHistoryCoordinator(
        hass, mock_config_entry, mock_energy_site, SITE_NAME
    )
    end_date = (tomorrow - timedelta(seconds=1)).isoformat()
    history_responses[end_date] = _history(
        *before,
        ((day + timedelta(hours=23, minutes=50)).isoformat(), {GRID: 30}),
        ((day + timedelta(hours=23, minutes=55)).isoformat(), {GRID: 40}),
        time_zone=time_zone,
    )
    history_responses[None] = _history(
        (tomorrow.isoformat(), {GRID: 20}),
        ((tomorrow + timedelta(minutes=5)).isoformat(), {GRID: 25}),
        time_zone=time_zone,
    )
    output = await _refresh(hass, coordinator)
    assert output[GRID] == 45
    assert output["_period_start"] == tomorrow
    mock_energy_site.energy_history.assert_called_with(
        TeslaEnergyPeriod.DAY, end_date=end_date
    )
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert [row["state"] for row in stats[GRID_STATISTIC_ID]] == expected_states
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 225
    await _refresh(hass, coordinator)
    assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == stats


@pytest.mark.parametrize("time_zone", ["UTC", "Asia/Kolkata"])
async def test_streaming_multi_day_history(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
    history_responses: dict[str | None, dict[str, Any]],
    time_zone: str,
) -> None:
    """Carry totals across days and sparse fields even when recorder writes lag."""
    zone = await dt_util.async_get_time_zone(time_zone)
    assert zone is not None
    day = datetime(2023, 6, 1, tzinfo=zone)
    last = day + timedelta(hours=23, minutes=55)
    history_responses[None] = _history(
        (last.isoformat(), {GRID: 1, SOLAR: 100}), time_zone=time_zone
    )
    await _refresh(hass, coordinator)
    history_responses[None] = _history(
        ((day + timedelta(days=4, minutes=5)).isoformat(), {GRID: 80, SOLAR: 50}),
        time_zone=time_zone,
    )
    history_responses[(day + timedelta(days=1, seconds=-1)).isoformat()] = _history(
        (last.isoformat(), {GRID: 10, SOLAR: 100}), time_zone=time_zone
    )
    for index in range(1, 4):
        history_responses[(day + timedelta(days=index + 1, seconds=-1)).isoformat()] = (
            _history(
                ((day + timedelta(days=index)).isoformat(), {GRID: index * 20}),
                ((last + timedelta(days=index)).isoformat(), {GRID: index * 20 + 10}),
                time_zone=time_zone,
            )
        )

    # Both jobs see the old recorder baseline; neither may skip ahead of its inputs.
    with patch.object(recorder_mock, "queue_task") as queue:
        for _ in range(2):
            mock_energy_site.energy_history.reset_mock()
            assert (await coordinator._async_update_data())[GRID] == 80
            await hass.async_block_till_done(wait_background_tasks=True)
            assert mock_energy_site.energy_history.call_args_list == [
                call(TeslaEnergyPeriod.DAY),
                *(
                    call(
                        TeslaEnergyPeriod.DAY,
                        end_date=(day + timedelta(days=index, seconds=-1)).isoformat(),
                    )
                    for index in range(1, 5)
                ),
            ]
    for queued in queue.call_args_list:
        recorder_mock.queue_task(queued.args[0])
    await async_wait_recording_done(hass)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID, SOLAR_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 360
    assert stats[SOLAR_STATISTIC_ID][-1]["sum"] == 150


async def test_independent_baselines_and_new_fields(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    history_responses: dict[str | None, dict[str, Any]],
) -> None:
    """Respect each field's checkpoint and initialize new fields from today."""
    before = [
        ("2023-06-01T08:00:00-07:00", {GRID: 10, SOLAR: 100}),
        ("2023-06-01T09:00:00-07:00", {SOLAR: 200}),
    ]
    history_responses[None] = _history(*before)
    await _refresh(hass, coordinator)
    history_responses[END_DATE] = _history(
        *before,
        (
            "2023-06-01T09:05:00-07:00",
            {GRID: 30, SOLAR: 50, "battery_energy_exported": 1000},
        ),
    )
    history_responses[None] = _history(
        (AFTER, {GRID: 20, SOLAR: 400, "battery_energy_exported": 5})
    )
    await _refresh(hass, coordinator)
    expected = {
        GRID_STATISTIC_ID: 60,
        SOLAR_STATISTIC_ID: 750,
        f"tesla_fleet:{SITE_ID}_battery_energy_exported": 5,
    }
    stats = await _get_hourly_stats(hass, set(expected))
    assert {key: rows[-1]["sum"] for key, rows in stats.items()} == expected


@pytest.mark.parametrize(
    ("failure", "interval", "expires_at"),
    [
        pytest.param(TeslaFleetError(), 300, 1000, id="api"),
        pytest.param(InvalidToken(), 300, 0, id="invalid-token"),
        pytest.param(OAuthExpired(), 300, 0, id="expired-token"),
        pytest.param(RateLimited({"after": 600}), 600, 1000, id="rate-limit"),
        pytest.param(TimeoutError(), 300, 1000, id="timeout"),
        pytest.param(ClientConnectionError(), 300, 1000, id="connection"),
        pytest.param({}, 300, 1000, id="missing-response"),
        pytest.param(_history(), 300, 1000, id="empty-day"),
        pytest.param(_history((AFTER, {GRID: 10})), 300, 1000, id="wrong-day"),
    ],
)
async def test_history_errors_preserve_sensors_and_retry(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    failure: TeslaFleetError | TimeoutError | ClientConnectionError | dict[str, Any],
    interval: int,
    expires_at: int,
) -> None:
    """Recover history independently of today's sensor data without skipping gaps."""
    current = _history((AFTER, {GRID: 20}))
    mock_energy_site.energy_history.side_effect = [
        _history((BEFORE, {GRID: 100})),
        current,
        failure,
        current,
        failure,
        current,
        _history((BEFORE, {GRID: 100}), (LAST, {GRID: 50})),
    ]
    hass.config_entries.async_update_entry(
        mock_config_entry, data={CONF_TOKEN: {"expires_at": 1000}}
    )
    await _refresh(hass, coordinator)
    previous = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    for _ in range(2):
        assert (await _refresh(hass, coordinator))[GRID] == 20
        assert coordinator.update_interval == timedelta(seconds=interval)
        assert mock_config_entry.data[CONF_TOKEN]["expires_at"] == expires_at
        assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == previous
    assert caplog.text.count("Unable to import statistics") == 1
    await _refresh(hass, coordinator)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 170
    assert coordinator.update_interval == ENERGY_HISTORY_INTERVAL
    assert "Statistics import recovered" in caplog.text


async def test_history_login_required(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
) -> None:
    """A background import can request reauthentication."""
    await _refresh(hass, coordinator)
    mock_energy_site.energy_history.side_effect = [
        _history((AFTER, {GRID: 20})),
        LoginRequired(),
    ]
    with patch("homeassistant.config_entries.ConfigEntry.async_start_reauth") as reauth:
        assert (await _refresh(hass, coordinator))[GRID] == 20
    reauth.assert_called_once_with(hass)


async def test_resume_valid_prefix_after_failure(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> None:
    """A restart resumes committed days without skipping a later failed request."""
    day_one = _history(("2023-06-01T23:55:00Z", {GRID: 10}), time_zone="UTC")
    current = _history(("2023-06-04T00:05:00Z", {GRID: 40}), time_zone="UTC")
    mock_energy_site.energy_history.side_effect = [
        _history(("2023-06-01T23:55:00Z", {GRID: 1}), time_zone="UTC"),
        current,
        day_one,
        TeslaFleetError(),
    ]
    await _refresh(hass, coordinator)
    assert (await _refresh(hass, coordinator))[GRID] == 40
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 10

    coordinator = TeslaFleetEnergySiteHistoryCoordinator(
        hass, mock_config_entry, mock_energy_site, SITE_NAME
    )
    mock_energy_site.energy_history.side_effect = [
        current,
        day_one,
        _history(("2023-06-02T23:55:00Z", {GRID: 20}), time_zone="UTC"),
        _history(("2023-06-03T23:55:00Z", {GRID: 30}), time_zone="UTC"),
    ]
    await _refresh(hass, coordinator)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 100


@pytest.mark.parametrize("time_zone", [None, "", "Invalid/Timezone"])
async def test_invalid_site_timezone(
    coordinator: TeslaFleetEnergySiteHistoryCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    time_zone: str | None,
) -> None:
    """Report unusable timezone metadata without guessing a zone or losing sensors."""
    mock_energy_site.energy_history.return_value = _history(
        (BEFORE, {GRID: 100}), time_zone=time_zone
    )
    assert (await _refresh(hass, coordinator))[GRID] == 100
    assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == {}
    assert "timezone" in caplog.text


@pytest.mark.parametrize(
    ("last_response", "cancelled_before_unload"),
    [
        pytest.param(_history((AFTER, {GRID: 30})), False, id="unload"),
        pytest.param(RateLimited({"after": 600}), True, id="rate-limit"),
    ],
)
async def test_one_import_job_and_unload(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_energy_history: AsyncMock,
    freezer: FrozenDateTimeFactory,
    last_response: dict[str, Any] | RateLimited,
    cancelled_before_unload: bool,
) -> None:
    """Current polling continues during an import, and unloading cancels that import."""
    mock_energy_history.return_value = _history((BEFORE, {GRID: 100}))
    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])
    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)
    previous = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    entered, release, cancelled = Event(), Event(), Event()

    get_current = AsyncMock(side_effect=[_history((AFTER, {GRID: 20})), last_response])

    async def get_historical() -> dict[str, Any]:
        entered.set()
        try:
            await release.wait()
        finally:
            cancelled.set()
        return _history((LAST, {GRID: 50}))

    async def get_history(
        period: TeslaEnergyPeriod, *, end_date: str | None = None
    ) -> dict[str, Any]:
        return await {None: get_current, END_DATE: get_historical}[end_date]()

    mock_energy_history.side_effect = get_history
    mock_energy_history.reset_mock()
    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await wait_for(entered.wait(), 5)
    freezer.tick(ENERGY_HISTORY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_energy_history.call_args_list == [
        call(TeslaEnergyPeriod.DAY),
        call(TeslaEnergyPeriod.DAY, end_date=END_DATE),
        call(TeslaEnergyPeriod.DAY),
    ]
    assert cancelled.is_set() is cancelled_before_unload
    assert await hass.config_entries.async_unload(normal_config_entry.entry_id)
    await wait_for(cancelled.wait(), 5)
    await async_wait_recording_done(hass)
    assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == previous
