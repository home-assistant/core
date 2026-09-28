"""Tests for selecting calendar-period statistics endpoints in SQL."""

from collections.abc import AsyncGenerator, Callable, Sequence
from datetime import datetime, timedelta
from typing import Literal
from unittest.mock import patch

import pytest
from sqlalchemy.engine.row import Row
from sqlalchemy.orm import Session

from homeassistant.components.recorder import Recorder, statistics
from homeassistant.components.recorder.db_schema import Statistics, StatisticsMeta
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.util import (
    execute_stmt_lambda_element,
    session_scope,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import async_wait_recording_done


@pytest.fixture
async def endpoint_session(
    recorder_mock: Recorder, hass: HomeAssistant
) -> AsyncGenerator[Session]:
    """Use Recorder's database and populate valid statistics metadata."""
    await hass.config.async_set_time_zone("UTC")
    await async_wait_recording_done(hass)
    with session_scope(session=recorder_mock.get_session()) as session:
        session.add_all(
            StatisticsMeta(
                id=metadata_id,
                statistic_id=f"test:statistic_{metadata_id}",
                source="test",
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                unit_class="energy",
                unit_of_measurement="kWh",
            )
            for metadata_id in range(1, 14)
        )
        session.commit()
        yield session


@pytest.mark.parametrize(
    ("days", "queries"),
    [
        pytest.param(399, 1, id="below-limit"),
        pytest.param(400, 1, id="at-limit"),
        pytest.param(401, 2, id="two-batches"),
        pytest.param(801, 3, id="three-batches"),
    ],
)
async def test_endpoint_query_batches(
    endpoint_session: Session, days: int, queries: int
) -> None:
    """Select the last row, including NULL and decreasing sums, across batches."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    sums = [5.0, None, 2.0]
    endpoint_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(days=day, hours=hour)).timestamp(),
            sum=sums[day % 3],
        )
        for metadata_id in (1, 2)
        for day in range(days)
        for hour in (0, 23)
    )
    endpoint_session.commit()
    with patch.object(
        statistics, "execute_stmt_lambda_element", wraps=execute_stmt_lambda_element
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            endpoint_session,
            start,
            start + timedelta(days=days),
            [1, 2],
            statistics.reduce_day_ts_factory()[1],
            {"sum"},
            4000,
        )
    assert execute.call_count == queries
    assert [(row.metadata_id, row.start_ts, row.sum) for row in rows] == [
        (
            metadata_id,
            (start + timedelta(days=day, hours=23)).timestamp(),
            sums[day % 3],
        )
        for metadata_id in (1, 2)
        for day in range(days)
    ]


async def test_endpoint_parameter_budget(endpoint_session: Session) -> None:
    """Split both sensors and periods without dropping or duplicating rows."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    endpoint_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(days=day)).timestamp(),
            sum=float(day),
        )
        for metadata_id in range(1, 14)
        for day in range(5)
    )
    endpoint_session.commit()
    with patch.object(
        statistics, "execute_stmt_lambda_element", wraps=execute_stmt_lambda_element
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            endpoint_session,
            start,
            start + timedelta(days=5),
            list(range(1, 14)),
            statistics.reduce_day_ts_factory()[1],
            {"sum"},
            10,
        )
    assert execute.call_count == 10
    assert [(row.metadata_id, row.sum) for row in rows] == [
        (metadata_id, float(day)) for metadata_id in range(1, 14) for day in range(5)
    ]
    for call in execute.call_args_list:
        compiled = call.args[1].compile(
            dialect=endpoint_session.bind.dialect,
            compile_kwargs={"render_postcompile": True},
        )
        assert len(compiled.positiontup or compiled.params) <= 10


def _unoptimized_statistics(
    session: Session,
    start_time: datetime,
    end_time: datetime | None,
    metadata_ids: list[int] | None,
    period_start_end: Callable[[float], tuple[float, float]],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
    max_bind_vars: int,
) -> Sequence[Row]:
    """Execute the unoptimized query path for result comparison."""
    return execute_stmt_lambda_element(
        session,
        statistics._generate_statistics_during_period_stmt(
            start_time, end_time, metadata_ids, Statistics, types
        ),
        orm_rows=False,
    )


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.freeze_time("2024-10-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "timezone",
    [
        pytest.param("UTC", id="utc"),
        pytest.param("Europe/Amsterdam", id="daylight-saving"),
        pytest.param("America/Havana", id="repeated-midnight"),
    ],
)
@pytest.mark.parametrize(
    "period",
    [pytest.param(period, id=period) for period in ("day", "week", "month", "year")],
)
@pytest.mark.parametrize(
    "types",
    [
        pytest.param({"sum"}, id="sum"),
        pytest.param({"change"}, id="change"),
        pytest.param({"sum", "change", "state", "last_reset"}, id="all-endpoint-types"),
    ],
)
@pytest.mark.parametrize(
    "end_time",
    [
        pytest.param(None, id="unbounded"),
        pytest.param(datetime(2024, 11, 3, 3, tzinfo=dt_util.UTC), id="bounded"),
    ],
)
@pytest.mark.parametrize(
    "statistic_ids",
    [
        pytest.param(None, id="all-sensors"),
        pytest.param({"test:energy_a"}, id="selected-sensor"),
    ],
)
async def test_endpoint_statistics_return_last_row_per_period(
    hass: HomeAssistant,
    timezone: str,
    period: Literal["day", "week", "month", "year"],
    types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
    end_time: datetime | None,
    statistic_ids: set[str] | None,
) -> None:
    """Return the last statistics row for each calendar period."""
    await hass.config.async_set_time_zone(timezone)
    start = datetime(2024, 10, 26, tzinfo=dt_util.UTC)
    samples = [
        (-24, 8.0, 8.0),
        (0, 10.0, 10.0),
        (1, 12.0, 12.0),
        (23, 13.0, 1.0),
        (24, 15.0, 3.0),
        (25, 14.0, 2.0),
        (48, None, None),
        (71, None, None),
        (120, 20.0, 8.0),
        (192, 25.0, 13.0),
        (193, 26.0, 14.0),
        (194, 27.0, 15.0),
        (195, 28.0, 16.0),
        (2000, 30.0, 18.0),
    ]
    for sensor in ("test:energy_a", "test:energy_b"):
        statistics.async_add_external_statistics(
            hass,
            {
                "statistic_id": sensor,
                "source": "test",
                "name": sensor,
                "unit_class": "energy",
                "unit_of_measurement": "kWh",
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
            },
            [
                {
                    "start": start + timedelta(hours=hour),
                    "sum": total,
                    "state": state,
                    "last_reset": start + timedelta(hours=22),
                }
                for hour, total, state in samples
            ],
        )
    await async_wait_recording_done(hass)
    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics.statistics_during_period(
            hass, start, end_time, statistic_ids, period, {"energy": "Wh"}, types
        )
    assert baseline.call_count == 1
    actual = statistics.statistics_during_period(
        hass, start, end_time, statistic_ids, period, {"energy": "Wh"}, types
    )
    assert expected
    assert actual == expected


@pytest.mark.parametrize(
    ("metadata_ids", "bounds", "types", "same_key"),
    [
        pytest.param([2, 3], ((1.0, 2.0),), {"sum"}, True, id="different-parameters"),
        pytest.param(None, ((0.0, 86400.0),), {"sum"}, False, id="all-sensors"),
        pytest.param(
            [1],
            ((0.0, 86400.0), (86400.0, 172800.0)),
            {"sum"},
            False,
            id="different-period-count",
        ),
        pytest.param([1], ((0.0, 86400.0),), {"state"}, False, id="different-columns"),
    ],
)
def test_endpoint_statement_cache_key(
    metadata_ids: list[int] | None,
    bounds: tuple[tuple[float, float], ...],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
    same_key: bool,
) -> None:
    """Cache by query structure, without retaining sensor or timestamp values."""
    baseline = statistics._generate_statistics_period_stmt(
        [1], ((0.0, 86400.0),), {"sum"}
    )._generate_cache_key()
    actual = statistics._generate_statistics_period_stmt(
        metadata_ids, bounds, types
    )._generate_cache_key()
    assert baseline is not None
    assert actual is not None
    assert (actual == baseline) is same_key


@pytest.mark.parametrize(
    ("types", "same_key"),
    [
        pytest.param({"mean"}, True, id="same-columns"),
        pytest.param({"min"}, False, id="different-min-column"),
        pytest.param({"max"}, False, id="different-max-column"),
        pytest.param(
            {"mean", "min", "max"},
            False,
            id="different-all-aggregate-columns",
        ),
    ],
)
def test_aggregate_statement_cache_key(
    types: set[Literal["max", "mean", "min"]],
    same_key: bool,
) -> None:
    """Cache aggregate queries by selected columns."""
    baseline = statistics._generate_statistics_period_stmt(
        [1],
        ((0.0, 86400.0),),
        {"mean"},
    )._generate_cache_key()

    actual = statistics._generate_statistics_period_stmt(
        [2],
        ((1.0, 86401.0),),
        types,
    )._generate_cache_key()

    assert baseline is not None
    assert actual is not None
    assert (actual == baseline) is same_key


@pytest.mark.parametrize(
    ("metadata_ids", "same_key"),
    [
        pytest.param([2, 3], True, id="different-sensors"),
        pytest.param(None, False, id="all-sensors"),
    ],
)
def test_latest_start_statement_cache_key(
    metadata_ids: list[int] | None, same_key: bool
) -> None:
    """The latest-timestamp query must track the presence of the sensor filter."""
    baseline = statistics._generate_latest_statistics_start_stmt(
        [1]
    )._generate_cache_key()
    actual = statistics._generate_latest_statistics_start_stmt(
        metadata_ids
    )._generate_cache_key()
    assert baseline is not None
    assert actual is not None
    assert (actual == baseline) is same_key


async def test_endpoint_cached_statement_parameters(endpoint_session: Session) -> None:
    """Execute the same cached query shape with different sensors and periods."""
    endpoint_session.add_all(
        [
            Statistics(metadata_id=1, start_ts=0.0, sum=10.0),
            Statistics(metadata_id=2, start_ts=0.0, sum=30.0),
            Statistics(metadata_id=2, start_ts=86400.0, sum=20.0),
        ]
    )
    endpoint_session.commit()
    first = execute_stmt_lambda_element(
        endpoint_session,
        statistics._generate_statistics_period_stmt([1], ((0.0, 86400.0),), {"sum"}),
        orm_rows=False,
    )
    second = execute_stmt_lambda_element(
        endpoint_session,
        statistics._generate_statistics_period_stmt(
            [2], ((86400.0, 172800.0),), {"sum"}
        ),
        orm_rows=False,
    )
    assert [tuple(row) for row in first] == [(1, 0.0, 10.0)]
    assert [tuple(row) for row in second] == [(2, 86400.0, 20.0)]


@pytest.mark.parametrize(
    ("metadata_ids", "offset", "queries", "expected"),
    [
        pytest.param([3], 0, 2, [(3, 20.0)], id="ignore-unselected-future-data"),
        pytest.param([1], 0, 1, [], id="no-selected-data"),
        pytest.param([3], 24, 1, [], id="selected-data-before-request"),
        pytest.param([1, 2, 3], 0, 3, [(3, 20.0)], id="empty-first-sensor-batch"),
    ],
)
async def test_endpoint_unbounded_sensor_filter(
    endpoint_session: Session,
    metadata_ids: list[int],
    offset: int,
    queries: int,
    expected: list[tuple[int, float]],
) -> None:
    """Use only selected sensors to determine the end of an unbounded request."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    endpoint_session.add_all(
        [
            Statistics(
                metadata_id=3,
                start_ts=(start + timedelta(hours=23)).timestamp(),
                sum=20.0,
            ),
            Statistics(
                metadata_id=13,
                start_ts=(start + timedelta(days=1200)).timestamp(),
                sum=50.0,
            ),
        ]
    )
    endpoint_session.commit()
    with patch.object(
        statistics, "execute_stmt_lambda_element", wraps=execute_stmt_lambda_element
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            endpoint_session,
            start + timedelta(hours=offset),
            None,
            metadata_ids,
            statistics.reduce_day_ts_factory()[1],
            {"sum"},
            4,
        )
    assert execute.call_count == queries
    assert [(row.metadata_id, row.sum) for row in rows] == expected


@pytest.mark.parametrize("timezone", ["UTC", "Europe/Amsterdam", "America/Havana"])
@pytest.mark.parametrize("period", ["day", "week", "month", "year"])
@pytest.mark.parametrize("start_month", [3, 10])
@pytest.mark.parametrize(
    ("unit_class", "statistic_unit", "requested_units"),
    [
        pytest.param("power", "W", {"power": "kW"}, id="power"),
        pytest.param(
            "temperature",
            "°C",
            {"temperature": "°F"},
            id="temperature",
        ),
    ],
)
@pytest.mark.parametrize(
    "statistic_ids", [None, {"test:statistic_1", "test:statistic_2"}]
)
@pytest.mark.parametrize("bounded", [False, True])
async def test_arithmetic_mean_returns_average_per_period(
    endpoint_session: Session,
    hass: HomeAssistant,
    timezone: str,
    period: Literal["day", "week", "month", "year"],
    start_month: int,
    unit_class: str,
    statistic_unit: str,
    requested_units: dict[str, str],
    statistic_ids: set[str] | None,
    bounded: bool,
) -> None:
    """Return the arithmetic average for each calendar period."""
    await hass.config.async_set_time_zone(timezone)
    endpoint_session.query(StatisticsMeta).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: unit_class,
            StatisticsMeta.unit_of_measurement: statistic_unit,
            StatisticsMeta.has_sum: False,
        }
    )

    start = datetime(2024, start_month, 26, 7, tzinfo=dt_util.UTC)
    samples = [
        (0, -1500.0),
        (1, 3000.0),
        (18, None),
        (24, 400.0),
        (25, 900.0),
        (48, None),
        (49, None),
        (120, 100.0),
        (20000, 700.0),
    ]

    endpoint_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(hours=hour)).timestamp(),
            mean=value,
            mean_weight=float(hour + 1),
        )
        for metadata_id in (1, 2)
        for hour, value in samples
    )
    endpoint_session.commit()

    end_time = {False: None, True: start + timedelta(days=10)}[bounded]

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics._statistics_during_period_with_session(
            hass,
            endpoint_session,
            start,
            end_time,
            statistic_ids,
            period,
            requested_units,
            {"mean"},
        )

    assert baseline.call_count == 1

    actual = statistics._statistics_during_period_with_session(
        hass,
        endpoint_session,
        start,
        end_time,
        statistic_ids,
        period,
        requested_units,
        {"mean"},
    )

    assert actual.keys() == expected.keys()
    for statistic_id, rows in expected.items():
        assert len(actual[statistic_id]) == len(rows)
        for actual_row, expected_row in zip(
            actual[statistic_id],
            rows,
            strict=True,
        ):
            assert actual_row == pytest.approx(
                expected_row,
                rel=1e-12,
                abs=1e-12,
            )


@pytest.mark.parametrize("period", ["day", "week", "month", "year"])
@pytest.mark.parametrize(
    "types",
    [
        pytest.param({"min"}, id="min"),
        pytest.param({"max"}, id="max"),
        pytest.param({"min", "max"}, id="min-max"),
        pytest.param({"mean", "min"}, id="mean-min"),
        pytest.param({"mean", "max"}, id="mean-max"),
        pytest.param({"mean", "min", "max"}, id="mean-min-max"),
    ],
)
async def test_aggregate_statistics_return_reduced_values_per_period(
    endpoint_session: Session,
    hass: HomeAssistant,
    period: Literal["day", "week", "month", "year"],
    types: set[Literal["max", "mean", "min"]],
) -> None:
    """Return reduced aggregate values for each calendar period."""
    endpoint_session.query(StatisticsMeta).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "temperature",
            StatisticsMeta.unit_of_measurement: "°C",
            StatisticsMeta.has_sum: False,
        }
    )

    start = datetime(2024, 3, 26, 7, tzinfo=dt_util.UTC)

    samples = [
        (0, 10.0, 5.0, 15.0),
        (1, 20.0, 8.0, 25.0),
        (18, None, None, None),
        (24, 30.0, 18.0, 35.0),
        (25, 40.0, 22.0, 50.0),
        (48, None, None, None),
        (120, 5.0, -10.0, 12.0),
    ]

    endpoint_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(hours=hour)).timestamp(),
            mean=mean,
            min=minimum,
            max=maximum,
        )
        for metadata_id in (1, 2)
        for hour, mean, minimum, maximum in samples
    )
    endpoint_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics._statistics_during_period_with_session(
            hass,
            endpoint_session,
            start,
            start + timedelta(days=10),
            {"test:statistic_1", "test:statistic_2"},
            period,
            {"temperature": "°F"},
            types,
        )

    assert baseline.call_count == 1

    actual = statistics._statistics_during_period_with_session(
        hass,
        endpoint_session,
        start,
        start + timedelta(days=10),
        {"test:statistic_1", "test:statistic_2"},
        period,
        {"temperature": "°F"},
        types,
    )

    assert actual.keys() == expected.keys()
    for statistic_id, rows in expected.items():
        assert len(actual[statistic_id]) == len(rows)
        for actual_row, expected_row in zip(actual[statistic_id], rows, strict=True):
            assert actual_row == pytest.approx(
                expected_row,
                rel=1e-12,
                abs=1e-12,
            )


@pytest.mark.parametrize(
    "statistic_ids",
    [
        pytest.param(None, id="all-statistics"),
        pytest.param(
            {"test:statistic_1", "test:statistic_2"},
            id="selected-statistics",
        ),
    ],
)
async def test_aggregate_statistics_allow_missing_mean(
    endpoint_session: Session,
    hass: HomeAssistant,
    statistic_ids: set[str] | None,
) -> None:
    """Allow aggregate requests for statistics without a mean."""
    endpoint_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "temperature",
            StatisticsMeta.unit_of_measurement: "°C",
            StatisticsMeta.has_sum: False,
        }
    )
    endpoint_session.query(StatisticsMeta).filter(StatisticsMeta.id == 2).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.NONE,
            StatisticsMeta.unit_class: "temperature",
            StatisticsMeta.unit_of_measurement: "°C",
            StatisticsMeta.has_sum: False,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    endpoint_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=10.0,
                min=5.0,
                max=15.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=20.0,
                min=8.0,
                max=25.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=start.timestamp(),
                mean=None,
                min=2.0,
                max=12.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=None,
                min=4.0,
                max=18.0,
            ),
        ]
    )
    endpoint_session.commit()

    types: set[Literal["max", "mean", "min"]] = {"mean", "min", "max"}

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics._statistics_during_period_with_session(
            hass,
            endpoint_session,
            start,
            start + timedelta(days=1),
            statistic_ids,
            "day",
            None,
            types,
        )

    assert baseline.call_count == 1

    actual = statistics._statistics_during_period_with_session(
        hass,
        endpoint_session,
        start,
        start + timedelta(days=1),
        statistic_ids,
        "day",
        None,
        types,
    )

    assert actual == expected
    assert actual["test:statistic_1"][0]["mean"] == pytest.approx(15.0)
    assert actual["test:statistic_1"][0]["min"] == 5.0
    assert actual["test:statistic_1"][0]["max"] == 25.0
    assert actual["test:statistic_2"][0]["mean"] is None
    assert actual["test:statistic_2"][0]["min"] == 2.0
    assert actual["test:statistic_2"][0]["max"] == 18.0


@pytest.mark.parametrize(
    ("days", "budget", "queries"), [(401, 4000, 2), (5, 4, 5), (5, 3, 10)]
)
async def test_arithmetic_mean_query_limits(
    endpoint_session: Session, days: int, budget: int, queries: int
) -> None:
    """Bound UNION terms and bind parameters without weighting arithmetic means."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    endpoint_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(days=day, hours=hour)).timestamp(),
            mean=value,
            mean_weight=weight,
        )
        for metadata_id in (1, 2)
        for day in range(days)
        for hour, value, weight in ((0, 100.0, 1.0), (1, 300.0, 99.0), (2, None, 0.0))
    )
    endpoint_session.commit()
    with patch.object(
        statistics, "execute_stmt_lambda_element", wraps=execute_stmt_lambda_element
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            endpoint_session,
            start,
            start + timedelta(days=days),
            [1, 2],
            statistics.reduce_day_ts_factory()[1],
            {"mean"},
            budget,
        )
    assert execute.call_count == queries
    assert [(r.metadata_id, r.start_ts, r.mean) for r in rows] == [
        (metadata_id, (start + timedelta(days=day)).timestamp(), 200.0)
        for metadata_id in (1, 2)
        for day in range(days)
    ]
    for call in execute.call_args_list:
        compiled = call.args[1].compile(
            dialect=endpoint_session.get_bind().dialect,
            compile_kwargs={"render_postcompile": True},
        )
        assert len(compiled.positiontup or compiled.params) <= budget


@pytest.mark.parametrize(
    ("unit_class", "unit", "mean_type", "period", "types"),
    [
        pytest.param(
            "power", "W", StatisticMeanType.ARITHMETIC, "hour", {"mean"}, id="hour"
        ),
        pytest.param(
            "angle", "°", StatisticMeanType.CIRCULAR, "day", {"mean"}, id="circular"
        ),
    ],
)
async def test_mean_fallback(
    endpoint_session: Session,
    hass: HomeAssistant,
    unit_class: str,
    unit: str,
    mean_type: StatisticMeanType,
    period: Literal["hour", "day"],
    types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
) -> None:
    """Retain the existing path for unoptimized requests."""
    endpoint_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.unit_class: unit_class,
            StatisticsMeta.unit_of_measurement: unit,
            StatisticsMeta.mean_type: mean_type,
        }
    )
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    endpoint_session.add(
        Statistics(
            metadata_id=1,
            start_ts=start.timestamp(),
            mean=100.0,
            mean_weight=1.0,
            min=50.0,
        )
    )
    endpoint_session.commit()
    with patch.object(statistics, "_get_statistics_period_rows") as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            endpoint_session,
            start,
            start + timedelta(hours=1),
            {"test:statistic_1"},
            period,
            None,
            types,
        )
    optimized.assert_not_called()
    assert result["test:statistic_1"]


async def test_aggregate_cached_parameters(endpoint_session: Session) -> None:
    """Do not leak sensor or time bounds between equal aggregate query shapes."""
    endpoint_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=0.0,
                mean=10.0,
                min=5.0,
                max=15.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=0.0,
                mean=30.0,
                min=20.0,
                max=40.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=86400.0,
                mean=20.0,
                min=10.0,
                max=25.0,
            ),
        ]
    )
    endpoint_session.commit()

    types: set[Literal["max", "mean", "min"]] = {"mean", "min", "max"}

    first = execute_stmt_lambda_element(
        endpoint_session,
        statistics._generate_statistics_period_stmt(
            [1],
            ((0.0, 86400.0),),
            types,
        ),
        orm_rows=False,
    )

    second = execute_stmt_lambda_element(
        endpoint_session,
        statistics._generate_statistics_period_stmt(
            [2],
            ((86400.0, 172800.0),),
            types,
        ),
        orm_rows=False,
    )

    assert [tuple(row) for row in first] == [(1, 0.0, 10.0, 5.0, 15.0)]
    assert [tuple(row) for row in second] == [(2, 86400.0, 20.0, 10.0, 25.0)]
