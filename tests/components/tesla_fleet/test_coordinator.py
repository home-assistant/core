"""Tests for Tesla Fleet historical energy statistics."""

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, call, patch

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
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
from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    async_import_statistics,
    statistics_during_period,
)
from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.coordinator import ENERGY_STATISTICS_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_TOKEN, Platform, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from . import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done

SITE_ID = "123456"
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


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration and wait for its first statistics import."""
    await setup_platform(hass, config_entry, [])
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_wait_recording_done(hass)


async def _advance(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    interval: timedelta = ENERGY_STATISTICS_INTERVAL,
) -> None:
    """Advance to the next scheduled import and let it run."""
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run the next hourly import and wait for recorder to write it."""
    await _advance(hass, freezer)
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
def history_responses(
    mock_energy_history: AsyncMock,
) -> dict[str | None, dict[str, Any]]:
    """Serve daily responses keyed by their requested end date."""
    responses: dict[str | None, dict[str, Any]] = {}

    def get_history(
        period: TeslaEnergyPeriod, *, end_date: str | None = None
    ) -> dict[str, Any]:
        assert period is TeslaEnergyPeriod.DAY
        return deepcopy(responses[end_date])

    mock_energy_history.side_effect = get_history
    return responses


async def test_hourly_aggregation_and_repeated_refresh(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
) -> None:
    """Bucket samples by UTC hour, skip untimed ones, and replace the latest hour."""
    mock_energy_history.return_value = _history(
        ("2023-06-01T08:12:34-07:00", {GRID: 100, SOLAR: 200}),
        ("2023-06-01T15:30:00Z", {GRID: 150}),
        ("2023-06-01T08:45:00-07:00", {GRID: 50}),
        ("2023-06-01T09:00:00-07:00", {GRID: 75, SOLAR: 100}),
        (None, {GRID: 1000}),
    )
    await _setup(hass, normal_config_entry)
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

    mock_energy_history.return_value["response"]["time_series"].extend(
        [
            {"timestamp": "2023-06-01T09:05:00-07:00", GRID: 25},
            {"timestamp": "2023-06-01T10:00:00-07:00", GRID: 75},
        ]
    )
    await _refresh(hass, freezer)
    stats = await _get_hourly_stats(hass, ids)
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-01T15:00:00+00:00", 300, 300),
        ("2023-06-01T16:00:00+00:00", 100, 400),
        ("2023-06-01T17:00:00+00:00", 75, 475),
    ]
    await _refresh(hass, freezer)
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
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    history_responses: dict[str | None, dict[str, Any]],
    time_zone: str,
    before: str,
    missing: str,
    expected: list[tuple[str, float, float]],
) -> None:
    """Recover the actual UTC hours across midnight and daylight-saving changes."""
    history_responses[None] = _history((before, {GRID: 100}), time_zone=time_zone)
    await _setup(hass, normal_config_entry)
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
    await _refresh(hass, freezer)
    mock_energy_history.assert_called_with(TeslaEnergyPeriod.DAY, end_date=end_date)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == expected
    await _refresh(hass, freezer)
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
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
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
    await _setup(hass, normal_config_entry)

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
    await _refresh(hass, freezer)

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
    recorder_mock: Recorder,
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    history_responses: dict[str | None, dict[str, Any]],
    first_values: dict[str, float],
) -> None:
    """Keep sums correct when a repeat import reads uncommitted baselines."""
    history_responses[None] = _history((BEFORE, {GRID: 100}))
    await _setup(hass, normal_config_entry)
    history_responses[None] = _history((AFTER, first_values))
    history_responses[END_DATE] = _history((BEFORE, {GRID: 100}), (LAST, {GRID: 50}))
    with patch.object(recorder_mock, "queue_task") as queue:
        await _advance(hass, freezer)
        history_responses[None] = _history((AFTER, {GRID: 20}))
        await _advance(hass, freezer)
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
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    history_responses: dict[str | None, dict[str, Any]],
    past_values: dict[str, float],
    current_values: dict[str, float],
    expected: list[tuple[str, float, float]],
) -> None:
    """An inactive field cannot make already imported days a permanent dependency."""
    old = _history((BEFORE, {GRID: 100, DISCHARGE: 10}))
    history_responses[None] = old
    await _setup(hass, normal_config_entry)
    history_responses[END_DATE] = old
    history_responses[None] = _history((AFTER, {GRID: 20}))
    await _refresh(hass, freezer)

    history_responses[END_DATE] = _history()
    history_responses[None] = _history(
        (AFTER, {GRID: 20}),
        ("2023-06-02T01:05:00-07:00", {GRID: 30}),
    )
    mock_energy_history.reset_mock()
    await _refresh(hass, freezer)
    mock_energy_history.assert_called_once_with(TeslaEnergyPeriod.DAY, end_date=None)
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
    mock_energy_history.reset_mock()
    await _refresh(hass, freezer)
    assert mock_energy_history.call_args_list == [
        call(TeslaEnergyPeriod.DAY, end_date=None),
        call(TeslaEnergyPeriod.DAY, end_date="2023-06-02T23:59:59-07:00"),
    ]
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID, DISCHARGE_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 200
    assert _hourly_rows(stats[DISCHARGE_STATISTIC_ID]) == expected


async def test_independent_baselines_and_new_fields(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    history_responses: dict[str | None, dict[str, Any]],
) -> None:
    """Respect each field's own baseline and initialize new fields from today."""
    before = [
        ("2023-06-01T08:00:00-07:00", {GRID: 10, SOLAR: 100}),
        ("2023-06-01T09:00:00-07:00", {SOLAR: 200}),
    ]
    history_responses[None] = _history(*before)
    await _setup(hass, normal_config_entry)
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
    await _refresh(hass, freezer)
    expected = {
        GRID_STATISTIC_ID: 60,
        SOLAR_STATISTIC_ID: 750,
        f"tesla_fleet:{SITE_ID}_battery_energy_exported": 5,
    }
    stats = await _get_hourly_stats(hass, set(expected))
    assert {key: rows[-1]["sum"] for key, rows in stats.items()} == expected


async def test_copy_sensor_history(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    history_responses: dict[str | None, dict[str, Any]],
) -> None:
    """Start a new statistic from its sensor's history, in Wh per hour."""
    sensor = entity_registry.async_get_or_create(
        Platform.SENSOR, DOMAIN, f"{SITE_ID}-{GRID}"
    )
    async_import_statistics(
        hass,
        StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=None,
            source=RECORDER_DOMAIN,
            statistic_id=sensor.entity_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        [
            StatisticData(start=datetime.fromisoformat(start), state=state, sum=total)
            for start, state, total in (
                ("2023-06-02T04:00:00+00:00", 2.0, 0.0),
                ("2023-06-02T05:00:00+00:00", 2.1, 0.1),
                ("2023-06-02T06:00:00+00:00", 2.25, 0.25),
                # From the first import onward, Tesla's history is used instead.
                ("2023-06-02T07:00:00+00:00", 0.4, 0.4),
            )
        ],
    )
    await async_wait_recording_done(hass)
    history_responses[None] = _history((AFTER, {GRID: 20}))
    history_responses[END_DATE] = _history((LAST, {GRID: 50}))

    await _setup(hass, normal_config_entry)

    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-02T04:00:00+00:00", 0, 0),
        ("2023-06-02T05:00:00+00:00", 100, 100),
        ("2023-06-02T06:00:00+00:00", 50, 150),
        ("2023-06-02T07:00:00+00:00", 20, 170),
    ]


@pytest.mark.parametrize(
    ("failure", "invalidates_token"),
    [
        pytest.param(TeslaFleetError(), False, id="api"),
        pytest.param(InvalidToken(), True, id="invalid-token"),
        pytest.param(OAuthExpired(), True, id="expired-token"),
        pytest.param(TimeoutError(), False, id="timeout"),
        pytest.param(ClientConnectionError(), False, id="connection"),
        pytest.param({}, False, id="missing-response"),
        pytest.param(_history(), False, id="empty-day"),
        pytest.param(_history((AFTER, {GRID: 10})), False, id="wrong-day"),
    ],
)
async def test_history_errors_retry_without_skipping(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
    failure: TeslaFleetError | TimeoutError | ClientConnectionError | dict[str, Any],
    invalidates_token: bool,
) -> None:
    """A failed historical day is retried later without skipping the gap."""
    current = _history((AFTER, {GRID: 20}))
    mock_energy_history.side_effect = [
        _history((BEFORE, {GRID: 100})),
        current,
        failure,
        current,
        failure,
        current,
        _history((BEFORE, {GRID: 100}), (LAST, {GRID: 50})),
    ]
    await _setup(hass, normal_config_entry)
    previous = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    for _ in range(2):
        await _refresh(hass, freezer)
        assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == previous
    assert (
        normal_config_entry.data[CONF_TOKEN]["expires_at"] == 0
    ) is invalidates_token
    await _refresh(hass, freezer)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 170


async def test_history_rate_limit_backoff(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
) -> None:
    """A rate-limited import retries after Tesla's requested delay."""
    mock_energy_history.side_effect = [
        _history((BEFORE, {GRID: 100})),
        _history((AFTER, {GRID: 20})),
        RateLimited({"after": 600}),
        _history((AFTER, {GRID: 20})),
        _history((BEFORE, {GRID: 100}), (LAST, {GRID: 50})),
    ]
    await _setup(hass, normal_config_entry)
    await _refresh(hass, freezer)
    assert mock_energy_history.call_count == 3

    await _advance(hass, freezer, timedelta(seconds=600))
    await async_wait_recording_done(hass)
    assert mock_energy_history.call_count == 5
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert stats[GRID_STATISTIC_ID][-1]["sum"] == 170


async def test_history_login_required(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
) -> None:
    """An import that needs new credentials starts reauthentication."""
    await _setup(hass, normal_config_entry)
    mock_energy_history.side_effect = [
        _history((AFTER, {GRID: 20})),
        LoginRequired(),
    ]
    await _refresh(hass, freezer)
    assert any(normal_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_resume_valid_prefix_after_failure(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_energy_history: AsyncMock,
) -> None:
    """Resume from recorder's committed prefix after a failed historical day."""
    day_one = _history(("2023-06-01T23:55:00Z", {GRID: 10}), time_zone="UTC")
    current = _history(("2023-06-04T00:05:00Z", {GRID: 40}), time_zone="UTC")
    mock_energy_history.side_effect = [
        _history(("2023-06-01T23:55:00Z", {GRID: 1}), time_zone="UTC"),
        current,
        day_one,
        TeslaFleetError(),
    ]
    await _setup(hass, normal_config_entry)
    await _refresh(hass, freezer)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-01T23:00:00+00:00", 10, 10)
    ]

    mock_energy_history.side_effect = [
        current,
        day_one,
        _history(("2023-06-02T23:55:00Z", {GRID: 20}), time_zone="UTC"),
        _history(("2023-06-03T23:55:00Z", {GRID: 30}), time_zone="UTC"),
    ]
    await _refresh(hass, freezer)
    stats = await _get_hourly_stats(hass, {GRID_STATISTIC_ID})
    assert _hourly_rows(stats[GRID_STATISTIC_ID]) == [
        ("2023-06-01T23:00:00+00:00", 10, 10),
        ("2023-06-02T23:00:00+00:00", 20, 30),
        ("2023-06-03T23:00:00+00:00", 30, 60),
        ("2023-06-04T00:00:00+00:00", 40, 100),
    ]


@pytest.mark.parametrize(
    ("time_zone", "message"),
    [
        pytest.param(
            None, "Energy history did not include the site's time zone", id="missing"
        ),
        pytest.param(
            "", "Energy history did not include the site's time zone", id="empty"
        ),
        pytest.param(
            "Invalid/Timezone",
            "Energy history included an unknown time zone: Invalid/Timezone",
            id="unknown",
        ),
    ],
)
async def test_invalid_site_timezone(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    mock_energy_history: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    time_zone: str | None,
    message: str,
) -> None:
    """Report unusable time zone metadata without guessing a zone."""
    mock_energy_history.return_value = _history(
        (BEFORE, {GRID: 100}), time_zone=time_zone
    )
    await _setup(hass, normal_config_entry)
    assert await _get_hourly_stats(hass, {GRID_STATISTIC_ID}) == {}
    assert message in caplog.text
