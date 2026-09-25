"""Tests for Tesla Fleet historical energy statistics."""

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, call, patch

from aiohttp import ClientConnectionError
import pytest
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
    TeslaFleetEnergySiteStatisticsCoordinator,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import UID

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done

SITE_ID = "123456"
SITE_NAME = "Energy Site"
SITE_TIME_ZONE = "America/Los_Angeles"
GRID = "grid_energy_imported"
SOLAR = "solar_energy_exported"
GRID_STATISTIC_ID = f"tesla_fleet:{SITE_ID}_{GRID}"
SOLAR_STATISTIC_ID = f"tesla_fleet:{SITE_ID}_{SOLAR}"
DISCHARGE = "total_battery_discharge"
DISCHARGE_STATISTIC_ID = f"tesla_fleet:{SITE_ID}_{DISCHARGE}"
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
    hass: HomeAssistant, coordinator: TeslaFleetEnergySiteStatisticsCoordinator
) -> None:
    """Run one import and wait for recorder to write it."""
    await coordinator.async_refresh()
    await async_wait_recording_done(hass)


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


def _hourly_rows(
    statistics: list[StatisticsRow],
) -> list[tuple[str, float | None, float | None]]:
    """Show recorded UTC timestamps alongside interval energy and cumulative sums."""
    return [
        (
            dt_util.utc_from_timestamp(row["start"]).isoformat(),
            row["state"],
            row["sum"],
        )
        for row in statistics
    ]


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
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> TeslaFleetEnergySiteStatisticsCoordinator:
    """Create a coordinator with an isolated recorder."""
    mock_config_entry.add_to_hass(hass)
    return TeslaFleetEnergySiteStatisticsCoordinator(
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


async def test_hourly_aggregation_and_repeated_refresh(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
) -> None:
    """Bucket samples by UTC hour, skip untimed ones, and replace the latest hour."""
    mock_energy_site.energy_history.return_value = _history(
        ("2023-06-01T08:12:34-07:00", {GRID: 100, SOLAR: 200}),
        ("2023-06-01T15:30:00Z", {GRID: 150}),
        ("2023-06-01T08:45:00-07:00", {GRID: 50}),
        ("2023-06-01T09:00:00-07:00", {GRID: 75, SOLAR: 100}),
        (None, {GRID: 1000}),
    )
    await _refresh(hass, coordinator)
    ids = {GRID_STATISTIC_ID, SOLAR_STATISTIC_ID}
    stats = await _get_hourly_stats(hass, ids)
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-01T15:00:00+00:00", 300, 300),
        ("2023-06-01T16:00:00+00:00", 75, 375),
    ]
    assert _hourly_rows(stats[SOLAR_STATISTIC_ID]) == [
        ("2023-06-01T15:00:00+00:00", 200, 200),
        ("2023-06-01T16:00:00+00:00", 100, 300),
    ]

    mock_energy_site.energy_history.return_value["response"]["time_series"].extend(
        [
            {"timestamp": "2023-06-01T09:05:00-07:00", GRID: 25},
            {"timestamp": "2023-06-01T10:00:00-07:00", GRID: 75},
        ]
    )
    await _refresh(hass, coordinator)
    stats = await _get_hourly_stats(hass, ids)
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-01T15:00:00+00:00", 300, 300),
        ("2023-06-01T16:00:00+00:00", 100, 400),
        ("2023-06-01T17:00:00+00:00", 75, 475),
    ]
    await _refresh(hass, coordinator)
    assert await _get_hourly_stats(hass, ids) == stats


@pytest.mark.parametrize(
    ("time_zone", "before", "missing", "expected"),
    [
        pytest.param(
            SITE_TIME_ZONE,
            BEFORE,
            LAST,
            [
                ("2023-06-02T06:00:00+00:00", 150, 150),
                ("2023-06-02T07:00:00+00:00", 20, 170),
            ],
            id="pacific",
        ),
        pytest.param(
            "Asia/Kolkata",
            "2023-06-01T23:45:00+05:30",
            "2023-06-01T23:55:00+05:30",
            [("2023-06-01T18:00:00+00:00", 170, 170)],
            id="half-hour",
        ),
        pytest.param(
            "Pacific/Chatham",
            "2023-06-01T23:45:00+12:45",
            "2023-06-01T23:55:00+12:45",
            [("2023-06-01T11:00:00+00:00", 170, 170)],
            id="quarter-hour",
        ),
        pytest.param(
            SITE_TIME_ZONE,
            "2023-03-12T01:55:00-08:00",
            "2023-03-12T03:00:00-07:00",
            [
                ("2023-03-12T09:00:00+00:00", 100, 100),
                ("2023-03-12T10:00:00+00:00", 50, 150),
                ("2023-03-13T07:00:00+00:00", 20, 170),
            ],
            id="spring-dst",
        ),
        pytest.param(
            SITE_TIME_ZONE,
            "2023-11-05T01:30:00-07:00",
            "2023-11-05T01:30:00-08:00",
            [
                ("2023-11-05T08:00:00+00:00", 100, 100),
                ("2023-11-05T09:00:00+00:00", 50, 150),
                ("2023-11-06T08:00:00+00:00", 20, 170),
            ],
            id="fall-dst",
        ),
    ],
)
async def test_backfill_after_midnight(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
    history_responses: dict[str | None, dict[str, Any]],
    time_zone: str,
    before: str,
    missing: str,
    expected: list[tuple[str, float, float]],
) -> None:
    """Recover the actual UTC hours across midnight and daylight-saving changes."""
    history_responses[None] = _history((before, {GRID: 100}), time_zone=time_zone)
    await _refresh(hass, coordinator)
    end_date = (
        datetime.fromisoformat(missing)
        .replace(hour=23, minute=59, second=59)
        .isoformat()
    )
    history_responses[end_date] = _history(
        (before, {GRID: 100}),
        (missing, {GRID: 50}),
        time_zone=time_zone,
    )
    current = datetime.fromisoformat(missing).replace(hour=0, minute=5) + timedelta(
        days=1
    )
    history_responses[None] = _history(
        (current.isoformat(), {GRID: 20}), time_zone=time_zone
    )
    await _refresh(hass, coordinator)
    mock_energy_site.energy_history.assert_called_with(
        TeslaEnergyPeriod.DAY, end_date=end_date
    )
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == expected
    await _refresh(hass, coordinator)
    assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == stats


@pytest.mark.parametrize(
    ("time_zone", "expected"),
    [
        pytest.param(
            "UTC",
            [
                ("2023-06-01T23:00:00+00:00", 10, 10),
                ("2023-06-02T00:00:00+00:00", 20, 30),
                ("2023-06-02T23:00:00+00:00", 30, 60),
                ("2023-06-03T00:00:00+00:00", 80, 140),
            ],
            id="whole-hour",
        ),
        pytest.param(
            "Asia/Kolkata",
            [
                ("2023-06-01T18:00:00+00:00", 30, 30),
                ("2023-06-02T18:00:00+00:00", 110, 140),
            ],
            id="half-hour",
        ),
    ],
)
async def test_multi_day_recovery(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    history_responses: dict[str | None, dict[str, Any]],
    time_zone: str,
    expected: list[tuple[str, float, float]],
) -> None:
    """Recover each missed hour across several days without lumping energy together."""
    zone = await dt_util.async_get_time_zone(time_zone)
    assert zone is not None
    day = datetime(2023, 6, 1, tzinfo=zone)
    last = day + timedelta(hours=23, minutes=55)
    history_responses[None] = _history(
        (last.isoformat(), {GRID: 1, SOLAR: 100}), time_zone=time_zone
    )
    await _refresh(hass, coordinator)

    history_responses[None] = _history(
        ((day + timedelta(days=2, minutes=5)).isoformat(), {GRID: 80, SOLAR: 50}),
        time_zone=time_zone,
    )
    history_responses[(day + timedelta(days=1, seconds=-1)).isoformat()] = _history(
        (last.isoformat(), {GRID: 10, SOLAR: 100}), time_zone=time_zone
    )
    history_responses[(day + timedelta(days=2, seconds=-1)).isoformat()] = _history(
        ((day + timedelta(days=1)).isoformat(), {GRID: 20}),
        ((last + timedelta(days=1)).isoformat(), {GRID: 30}),
        time_zone=time_zone,
    )
    await _refresh(hass, coordinator)

    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID, SOLAR_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == expected
    assert _hourly_rows(stats[SOLAR_STATISTIC_ID]) == [
        (expected[0][0], 100, 100),
        (expected[-1][0], 50, 150),
    ]


@pytest.mark.parametrize(
    "first_values", [{GRID: 20}, {}], ids=["new-hour", "same-hour"]
)
async def test_repeated_import_with_delayed_recorder(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    history_responses: dict[str | None, dict[str, Any]],
    first_values: dict[str, float],
) -> None:
    """Keep sums correct when a repeat import reads uncommitted baselines."""
    history_responses[None] = _history((BEFORE, {GRID: 100}))
    await _refresh(hass, coordinator)
    history_responses[None] = _history((AFTER, first_values))
    history_responses[END_DATE] = _history((BEFORE, {GRID: 100}), (LAST, {GRID: 50}))
    with patch.object(recorder_mock, "queue_task") as queue:
        await coordinator.async_refresh()
        history_responses[None] = _history((AFTER, {GRID: 20}))
        await coordinator.async_refresh()
    for queued in queue.call_args_list:
        recorder_mock.queue_task(queued.args[0])
    await async_wait_recording_done(hass)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-02T06:00:00+00:00", 150, 150),
        ("2023-06-02T07:00:00+00:00", 20, 170),
    ]


@pytest.mark.parametrize(
    ("past_values", "current_values", "expected"),
    [
        pytest.param(
            {},
            {},
            [("2023-06-02T06:00:00+00:00", 10, 10)],
            id="stays-absent",
        ),
        pytest.param(
            {DISCHARGE: 15},
            {DISCHARGE: 5},
            [
                ("2023-06-02T06:00:00+00:00", 10, 10),
                ("2023-06-03T06:00:00+00:00", 15, 25),
                ("2023-06-03T07:00:00+00:00", 5, 30),
            ],
            id="returns",
        ),
    ],
)
async def test_inactive_field_does_not_block_progress(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
    history_responses: dict[str | None, dict[str, Any]],
    past_values: dict[str, float],
    current_values: dict[str, float],
    expected: list[tuple[str, float, float]],
) -> None:
    """An inactive field cannot make already imported days a permanent dependency."""
    old = _history((BEFORE, {GRID: 100, DISCHARGE: 10}))
    history_responses[None] = old
    await _refresh(hass, coordinator)
    history_responses[END_DATE] = old
    history_responses[None] = _history((AFTER, {GRID: 20}))
    await _refresh(hass, coordinator)

    history_responses[END_DATE] = _history()
    history_responses[None] = _history(
        (AFTER, {GRID: 20}),
        ("2023-06-02T01:05:00-07:00", {GRID: 30}),
    )
    mock_energy_site.energy_history.reset_mock()
    await _refresh(hass, coordinator)
    mock_energy_site.energy_history.assert_called_once_with(
        TeslaEnergyPeriod.DAY, end_date=None
    )
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID, DISCHARGE_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-02T06:00:00+00:00", 100, 100),
        ("2023-06-02T07:00:00+00:00", 20, 120),
        ("2023-06-02T08:00:00+00:00", 30, 150),
    ]
    assert _hourly_rows(stats[DISCHARGE_STATISTIC_ID]) == [
        ("2023-06-02T06:00:00+00:00", 10, 10)
    ]

    history_responses["2023-06-02T23:59:59-07:00"] = _history(
        (AFTER, {GRID: 20}),
        ("2023-06-02T01:05:00-07:00", {GRID: 30}),
        ("2023-06-02T23:55:00-07:00", {GRID: 10, **past_values}),
    )
    history_responses[None] = _history(
        ("2023-06-03T00:05:00-07:00", {GRID: 40, **current_values})
    )
    mock_energy_site.energy_history.reset_mock()
    await _refresh(hass, coordinator)
    assert mock_energy_site.energy_history.call_args_list == [
        call(TeslaEnergyPeriod.DAY, end_date=None),
        call(TeslaEnergyPeriod.DAY, end_date="2023-06-02T23:59:59-07:00"),
    ]
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID, DISCHARGE_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 200
    assert _hourly_rows(stats[DISCHARGE_STATISTIC_ID]) == expected


async def test_independent_baselines_and_new_fields(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    history_responses: dict[str | None, dict[str, Any]],
) -> None:
    """Respect each field's own baseline and initialize new fields from today."""
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
    ("failure", "retry_after", "expires_at"),
    [
        pytest.param(TeslaFleetError(), None, 1000, id="api"),
        pytest.param(InvalidToken(), None, 0, id="invalid-token"),
        pytest.param(OAuthExpired(), None, 0, id="expired-token"),
        pytest.param(RateLimited({"after": 600}), 600, 1000, id="rate-limit"),
        pytest.param(TimeoutError(), None, 1000, id="timeout"),
        pytest.param(ClientConnectionError(), None, 1000, id="connection"),
        pytest.param({}, None, 1000, id="missing-response"),
        pytest.param(_history(), None, 1000, id="empty-day"),
        pytest.param(_history((AFTER, {GRID: 10})), None, 1000, id="wrong-day"),
    ],
)
async def test_history_errors_retry_without_skipping(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
    failure: TeslaFleetError | TimeoutError | ClientConnectionError | dict[str, Any],
    retry_after: float | None,
    expires_at: int,
) -> None:
    """A failed historical day is retried later without skipping the gap."""
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
        await _refresh(hass, coordinator)
        assert not coordinator.last_update_success
        assert getattr(coordinator.last_exception, "retry_after", None) == retry_after
        assert mock_config_entry.data[CONF_TOKEN]["expires_at"] == expires_at
        assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == previous
    await _refresh(hass, coordinator)
    assert coordinator.last_update_success
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 170


async def test_history_login_required(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> None:
    """An import that needs new credentials starts reauthentication."""
    await _refresh(hass, coordinator)
    mock_energy_site.energy_history.side_effect = [
        _history((AFTER, {GRID: 20})),
        LoginRequired(),
    ]
    await _refresh(hass, coordinator)
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_resume_valid_prefix_after_failure(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
) -> None:
    """Resume from recorder's committed prefix after a failed historical day."""
    day_one = _history(("2023-06-01T23:55:00Z", {GRID: 10}), time_zone="UTC")
    current = _history(("2023-06-04T00:05:00Z", {GRID: 40}), time_zone="UTC")
    mock_energy_site.energy_history.side_effect = [
        _history(("2023-06-01T23:55:00Z", {GRID: 1}), time_zone="UTC"),
        current,
        day_one,
        TeslaFleetError(),
    ]
    await _refresh(hass, coordinator)
    await _refresh(hass, coordinator)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-01T23:00:00+00:00", 10, 10)
    ]

    mock_energy_site.energy_history.side_effect = [
        current,
        day_one,
        _history(("2023-06-02T23:55:00Z", {GRID: 20}), time_zone="UTC"),
        _history(("2023-06-03T23:55:00Z", {GRID: 30}), time_zone="UTC"),
    ]
    await _refresh(hass, coordinator)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-01T23:00:00+00:00", 10, 10),
        ("2023-06-02T23:00:00+00:00", 20, 30),
        ("2023-06-03T23:00:00+00:00", 30, 60),
        ("2023-06-04T00:00:00+00:00", 40, 100),
    ]


@pytest.mark.parametrize("time_zone", [None, "", "Invalid/Timezone"])
async def test_invalid_site_timezone(
    coordinator: TeslaFleetEnergySiteStatisticsCoordinator,
    hass: HomeAssistant,
    mock_energy_site: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    time_zone: str | None,
) -> None:
    """Report unusable timezone metadata without guessing a zone."""
    mock_energy_site.energy_history.return_value = _history(
        (BEFORE, {GRID: 100}), time_zone=time_zone
    )
    await _refresh(hass, coordinator)
    assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == {}
    assert "timezone" in caplog.text
