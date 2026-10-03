"""Tests for selecting calendar-period statistics in SQL."""

from collections.abc import AsyncGenerator, Callable, Sequence
from datetime import datetime, timedelta
from typing import Literal
from unittest.mock import patch

import pytest
from sqlalchemy.engine.row import Row
from sqlalchemy.orm import Session

from homeassistant.components.recorder import Recorder, statistics
from homeassistant.components.recorder.db_schema import (
    Statistics,
    StatisticsMeta,
    StatisticsShortTerm,
)
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.util import (
    execute_stmt_lambda_element,
    session_scope,
)
from homeassistant.const import EntityStateAttribute, UnitOfEnergyDistance, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import async_wait_recording_done


@pytest.fixture
async def statistics_session(
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


def _unoptimized_statistics(
    session: Session,
    start_time: datetime,
    end_time: datetime | None,
    metadata_ids: list[int] | None,
    period_start_end: Callable[[float], tuple[float, float]],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
    max_bind_vars: int,
    mean_type: StatisticMeanType = StatisticMeanType.NONE,
) -> Sequence[Row]:
    """Execute the unoptimized query path for result comparison."""
    return execute_stmt_lambda_element(
        session,
        statistics._generate_statistics_during_period_stmt(
            start_time, end_time, metadata_ids, Statistics, types
        ),
        orm_rows=False,
    )


def test_period_statement_metadata_ids_do_not_use_driver_binds(
    statistics_session: Session,
) -> None:
    """Do not count metadata ids against the driver bind parameter budget."""
    stmt = statistics._generate_statistics_period_stmt(
        [1, 2, 3],
        (
            (0.0, 86400.0),
            (86400.0, 172800.0),
        ),
        {"mean"},
        StatisticMeanType.ARITHMETIC,
    )

    compiled = stmt.compile(
        dialect=statistics_session.get_bind().dialect,
        compile_kwargs={"render_postcompile": True},
    )

    assert len(compiled.positiontup or compiled.params) == 4


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
        [1],
        ((0.0, 86400.0),),
        {"sum"},
    )._generate_cache_key()
    actual = statistics._generate_statistics_period_stmt(
        metadata_ids,
        bounds,
        types,
    )._generate_cache_key()
    assert baseline is not None
    assert actual is not None
    assert (actual == baseline) is same_key


@pytest.mark.parametrize(
    ("types", "mean_type", "same_key"),
    [
        pytest.param(
            {"mean"},
            StatisticMeanType.ARITHMETIC,
            True,
            id="same-columns",
        ),
        pytest.param(
            {"min"},
            StatisticMeanType.NONE,
            False,
            id="different-min-column",
        ),
        pytest.param(
            {"max"},
            StatisticMeanType.NONE,
            False,
            id="different-max-column",
        ),
        pytest.param(
            {"mean", "min", "max"},
            StatisticMeanType.ARITHMETIC,
            False,
            id="different-all-aggregate-columns",
        ),
    ],
)
def test_aggregate_statement_cache_key(
    types: set[Literal["max", "mean", "min"]],
    mean_type: StatisticMeanType,
    same_key: bool,
) -> None:
    """Cache aggregate queries by selected columns."""
    baseline = statistics._generate_statistics_period_stmt(
        [1],
        ((0.0, 86400.0),),
        {"mean"},
        StatisticMeanType.ARITHMETIC,
    )._generate_cache_key()

    actual = statistics._generate_statistics_period_stmt(
        [2],
        ((1.0, 86401.0),),
        types,
        mean_type,
    )._generate_cache_key()

    assert baseline is not None
    assert actual is not None
    assert (actual == baseline) is same_key


def test_mean_type_changes_statement_cache_key() -> None:
    """Cache arithmetic and circular mean queries separately."""
    arithmetic = statistics._generate_statistics_period_stmt(
        [1],
        ((0.0, 86400.0),),
        {"mean"},
        StatisticMeanType.ARITHMETIC,
    )._generate_cache_key()

    circular = statistics._generate_statistics_period_stmt(
        [1],
        ((0.0, 86400.0),),
        {"mean"},
        StatisticMeanType.CIRCULAR,
    )._generate_cache_key()

    assert arithmetic is not None
    assert circular is not None
    assert arithmetic != circular


def test_mean_period_statement_requires_mean_type() -> None:
    """Require a mean type when mean is selected."""
    with pytest.raises(AssertionError):
        statistics._generate_statistics_period_stmt(
            [1],
            ((0.0, 86400.0),),
            {"mean"},
        )


@pytest.mark.parametrize(
    ("metadata_ids", "same_key"),
    [
        pytest.param([2, 3], True, id="different-sensors"),
        pytest.param(None, False, id="all-sensors"),
    ],
)
def test_start_end_statement_cache_key(
    metadata_ids: list[int] | None, same_key: bool
) -> None:
    """The range query must track the presence of the sensor filter."""
    baseline = statistics._generate_statistics_start_end_stmt([1])._generate_cache_key()

    actual = statistics._generate_statistics_start_end_stmt(
        metadata_ids
    )._generate_cache_key()

    assert baseline is not None
    assert actual is not None
    assert (actual == baseline) is same_key


async def test_endpoint_cached_statement_parameters(
    statistics_session: Session,
) -> None:
    """Execute the same cached query shape with different sensors and periods."""
    statistics_session.add_all(
        [
            Statistics(metadata_id=1, start_ts=0.0, sum=10.0),
            Statistics(metadata_id=2, start_ts=0.0, sum=30.0),
            Statistics(metadata_id=2, start_ts=86400.0, sum=20.0),
        ]
    )
    statistics_session.commit()
    first = execute_stmt_lambda_element(
        statistics_session,
        statistics._generate_statistics_period_stmt([1], ((0.0, 86400.0),), {"sum"}),
        orm_rows=False,
    )
    second = execute_stmt_lambda_element(
        statistics_session,
        statistics._generate_statistics_period_stmt(
            [2, 3], ((86400.0, 172800.0),), {"sum"}
        ),
        orm_rows=False,
    )
    assert [tuple(row) for row in first] == [(1, 0.0, 10.0)]
    assert [tuple(row) for row in second] == [(2, 86400.0, 20.0)]


async def test_aggregate_cached_parameters(statistics_session: Session) -> None:
    """Do not leak sensor or time bounds between equal aggregate query shapes."""
    statistics_session.add_all(
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
    statistics_session.commit()

    types: set[Literal["max", "mean", "min"]] = {"mean", "min", "max"}

    first = execute_stmt_lambda_element(
        statistics_session,
        statistics._generate_statistics_period_stmt(
            [1],
            ((0.0, 86400.0),),
            types,
            StatisticMeanType.ARITHMETIC,
        ),
        orm_rows=False,
    )

    second = execute_stmt_lambda_element(
        statistics_session,
        statistics._generate_statistics_period_stmt(
            [2],
            ((86400.0, 172800.0),),
            types,
            StatisticMeanType.ARITHMETIC,
        ),
        orm_rows=False,
    )

    assert [tuple(row) for row in first] == [(1, 0.0, 10.0, 5.0, 15.0)]
    assert [tuple(row) for row in second] == [(2, 86400.0, 20.0, 10.0, 25.0)]


async def test_mixed_cached_parameters(statistics_session: Session) -> None:
    """Do not leak sensor or time bounds between equal mixed query shapes."""
    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=0.0,
                mean=10.0,
                sum=20.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=0.0,
                mean=30.0,
                sum=40.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=86400.0,
                mean=50.0,
                sum=60.0,
            ),
        ]
    )
    statistics_session.commit()

    types = {"mean", "sum"}

    first = execute_stmt_lambda_element(
        statistics_session,
        statistics._generate_statistics_period_stmt(
            [1],
            ((0.0, 86400.0),),
            types,
            StatisticMeanType.ARITHMETIC,
        ),
        orm_rows=False,
    )

    second = execute_stmt_lambda_element(
        statistics_session,
        statistics._generate_statistics_period_stmt(
            [2],
            ((86400.0, 172800.0),),
            types,
            StatisticMeanType.ARITHMETIC,
        ),
        orm_rows=False,
    )

    assert [tuple(row) for row in first] == [(1, 0.0, 10.0, 20.0)]
    assert [tuple(row) for row in second] == [(2, 86400.0, 50.0, 60.0)]


@pytest.mark.parametrize(
    ("days", "queries"),
    [
        pytest.param(399, 1, id="below-limit"),
        pytest.param(400, 1, id="at-limit"),
        pytest.param(401, 2, id="two-batches"),
        pytest.param(800, 2, id="two-full-batches"),
        pytest.param(801, 4, id="range-lookup-and-three-batches"),
    ],
)
async def test_period_query_batches(
    statistics_session: Session, days: int, queries: int
) -> None:
    """Select the last row, including NULL and decreasing sums, across batches."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    sums = [5.0, None, 2.0]
    statistics_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(days=day, hours=hour)).timestamp(),
            sum=sums[day % 3],
        )
        for metadata_id in (1, 2)
        for day in range(days)
        for hour in (0, 23)
    )
    statistics_session.commit()
    with patch.object(
        statistics, "execute_stmt_lambda_element", wraps=execute_stmt_lambda_element
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            statistics_session,
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


async def test_period_query_bounded_clips_to_available_range(
    statistics_session: Session,
) -> None:
    """Clip a long bounded request to the selected statistics range."""
    start = datetime(2020, 1, 1, tzinfo=dt_util.UTC)
    data_start = start + timedelta(days=1200)

    statistics_session.add(
        Statistics(
            metadata_id=3,
            start_ts=(data_start + timedelta(hours=12)).timestamp(),
            sum=20.0,
        )
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "execute_stmt_lambda_element",
        wraps=execute_stmt_lambda_element,
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            statistics_session,
            start,
            start + timedelta(days=1600),
            [3],
            statistics.reduce_day_ts_factory()[1],
            {"sum"},
            4000,
        )

    # One range lookup and one clipped period query.
    assert execute.call_count == 2
    assert [(row.metadata_id, row.sum) for row in rows] == [(3, 20.0)]


async def test_period_parameter_budget(statistics_session: Session) -> None:
    """Split both sensors and periods without dropping or duplicating rows."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    statistics_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(days=day)).timestamp(),
            sum=float(day),
        )
        for metadata_id in range(1, 14)
        for day in range(5)
    )
    statistics_session.commit()
    with patch.object(
        statistics, "execute_stmt_lambda_element", wraps=execute_stmt_lambda_element
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            statistics_session,
            start,
            start + timedelta(days=5),
            list(range(1, 14)),
            statistics.reduce_day_ts_factory()[1],
            {"sum"},
            10,
        )
    assert execute.call_count == 2
    assert [(row.metadata_id, row.sum) for row in rows] == [
        (metadata_id, float(day)) for metadata_id in range(1, 14) for day in range(5)
    ]
    for call in execute.call_args_list:
        compiled = call.args[1].compile(
            dialect=statistics_session.bind.dialect,
            compile_kwargs={"render_postcompile": True},
        )
        assert len(compiled.positiontup or compiled.params) <= 10


async def test_unbounded_request_uses_row_based_path(
    statistics_session: Session,
    hass: HomeAssistant,
) -> None:
    """Use the row-based path for unbounded statistics requests."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                sum=10.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(days=10000)).timestamp(),
                sum=20.0,
            ),
        ]
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            None,
            {"test:statistic_1"},
            "day",
            None,
            {"sum"},
        )

    optimized.assert_not_called()

    assert [row["sum"] for row in result["test:statistic_1"]] == [
        10.0,
        20.0,
    ]


@pytest.mark.parametrize(
    ("days", "budget", "queries"),
    [
        (401, 4000, 2),
        (5, 4, 4),
        (5, 3, 6),
    ],
)
async def test_arithmetic_mean_query_limits(
    statistics_session: Session, days: int, budget: int, queries: int
) -> None:
    """Bound UNION terms and bind parameters without weighting arithmetic means."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    statistics_session.add_all(
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
    statistics_session.commit()
    with patch.object(
        statistics, "execute_stmt_lambda_element", wraps=execute_stmt_lambda_element
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            statistics_session,
            start,
            start + timedelta(days=days),
            [1, 2],
            statistics.reduce_day_ts_factory()[1],
            {"mean"},
            budget,
            StatisticMeanType.ARITHMETIC,
        )
    assert execute.call_count == queries
    assert [(r.metadata_id, r.start_ts, r.mean) for r in rows] == [
        (metadata_id, (start + timedelta(days=day)).timestamp(), 200.0)
        for metadata_id in (1, 2)
        for day in range(days)
    ]
    for call in execute.call_args_list:
        compiled = call.args[1].compile(
            dialect=statistics_session.get_bind().dialect,
            compile_kwargs={"render_postcompile": True},
        )
        assert len(compiled.positiontup or compiled.params) <= budget


async def test_circular_mean_query_limits(statistics_session: Session) -> None:
    """Account for circular mean expressions in the bind parameter budget."""
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(days=day, hours=hour)).timestamp(),
            mean=value,
            mean_weight=weight,
        )
        for metadata_id in (1, 2, 3)
        for day in range(3)
        for hour, value, weight in (
            (0, 350.0, 1.0),
            (1, 10.0, 1.0),
        )
    )
    statistics_session.commit()

    max_bind_vars = 10

    with patch.object(
        statistics,
        "execute_stmt_lambda_element",
        wraps=execute_stmt_lambda_element,
    ) as execute:
        rows = statistics._get_statistics_period_rows(
            statistics_session,
            start,
            start + timedelta(days=3),
            [1, 2, 3],
            statistics.reduce_day_ts_factory()[1],
            {"mean"},
            max_bind_vars,
            StatisticMeanType.CIRCULAR,
        )

    assert execute.call_count == 4
    assert [(row.metadata_id, row.start_ts, row.mean) for row in rows] == [
        (
            metadata_id,
            (start + timedelta(days=day)).timestamp(),
            pytest.approx(0.0, abs=1e-12),
        )
        for metadata_id in (1, 2, 3)
        for day in range(3)
    ]

    for call in execute.call_args_list:
        compiled = call.args[1].compile(
            dialect=statistics_session.get_bind().dialect,
            compile_kwargs={"render_postcompile": True},
        )
        assert len(compiled.positiontup or compiled.params) <= max_bind_vars


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
    statistic_ids: set[str] | None,
) -> None:
    """Return the last statistics row for each calendar period."""
    await hass.config.async_set_time_zone(timezone)
    start = datetime(2024, 10, 26, tzinfo=dt_util.UTC)
    end_time = datetime(2024, 11, 3, 3, tzinfo=dt_util.UTC)
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


async def test_reducer_flushes_final_dst_fallback_period(
    hass: HomeAssistant,
) -> None:
    """Flush the final aggregate period across DST fall-back."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")

    timezone = dt_util.get_default_time_zone()
    start = datetime(2025, 10, 26, tzinfo=timezone)
    end = datetime(2025, 10, 27, tzinfo=timezone)

    stats: dict[str, list[statistics.StatisticsRow]] = {
        "test:statistic_1": [
            {
                "start": start.timestamp(),
                "min": 10.0,
            }
        ]
    }

    result = statistics._reduce_statistics_per_day(
        stats,
        {"min"},
        {},
    )

    assert result["test:statistic_1"] == [
        {
            "start": start.timestamp(),
            "end": end.timestamp(),
            "min": 10.0,
        }
    ]


@pytest.mark.parametrize("timezone", ["UTC", "Europe/Amsterdam", "America/Havana"])
@pytest.mark.parametrize("period", ["day", "week", "month", "year"])
@pytest.mark.parametrize("start_month", [3, 10])
@pytest.mark.parametrize(
    "statistic_ids", [None, {"test:statistic_1", "test:statistic_2"}]
)
async def test_arithmetic_mean_returns_average_per_period(
    statistics_session: Session,
    hass: HomeAssistant,
    timezone: str,
    period: Literal["day", "week", "month", "year"],
    start_month: int,
    statistic_ids: set[str] | None,
) -> None:
    """Return the arithmetic average for each calendar period."""
    await hass.config.async_set_time_zone(timezone)
    statistics_session.query(StatisticsMeta).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "power",
            StatisticsMeta.unit_of_measurement: "W",
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

    statistics_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(hours=hour)).timestamp(),
            mean=value,
            mean_weight=float(hour + 1),
        )
        for metadata_id in (1, 2)
        for hour, value in samples
    )
    statistics_session.commit()

    end_time = start + timedelta(days=10)

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            end_time,
            statistic_ids,
            period,
            None,
            {"mean"},
        )

    assert baseline.call_count == 1

    actual = statistics._statistics_during_period_with_session(
        hass,
        statistics_session,
        start,
        end_time,
        statistic_ids,
        period,
        None,
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
    statistics_session: Session,
    hass: HomeAssistant,
    period: Literal["day", "week", "month", "year"],
    types: set[Literal["max", "mean", "min"]],
) -> None:
    """Return reduced aggregate values for each calendar period."""
    statistics_session.query(StatisticsMeta).update(
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

    statistics_session.add_all(
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
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=10),
            {"test:statistic_1", "test:statistic_2"},
            period,
            None,
            types,
        )

    assert baseline.call_count == 1

    actual = statistics._statistics_during_period_with_session(
        hass,
        statistics_session,
        start,
        start + timedelta(days=10),
        {"test:statistic_1", "test:statistic_2"},
        period,
        None,
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


@pytest.mark.parametrize("period", ["day", "week", "month", "year"])
@pytest.mark.parametrize(
    "types",
    [
        pytest.param({"mean", "sum"}, id="mean-sum"),
        pytest.param({"min", "state"}, id="min-state"),
        pytest.param({"max", "last_reset"}, id="max-last-reset"),
        pytest.param(
            {"mean", "min", "max", "sum", "state", "last_reset"},
            id="all-types",
        ),
        pytest.param(
            {"mean", "sum", "change", "state", "last_reset"},
            id="mean-sum-change-state-last-reset",
        ),
    ],
)
async def test_mixed_statistics_return_period_values(
    statistics_session: Session,
    hass: HomeAssistant,
    period: Literal["day", "week", "month", "year"],
    types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
) -> None:
    """Return aggregate and endpoint values for each calendar period."""
    statistics_session.query(StatisticsMeta).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "temperature",
            StatisticsMeta.unit_of_measurement: "°C",
            StatisticsMeta.has_sum: True,
        }
    )

    start = datetime(2024, 3, 26, 7, tzinfo=dt_util.UTC)

    samples = [
        # hour, mean, min, max, state, sum, reset_offset
        (0, 10.0, 5.0, 15.0, 100.0, 10.0, 0),
        (1, 20.0, 8.0, 25.0, 110.0, 20.0, 1),
        (18, None, None, None, 120.0, 30.0, 2),
        (24, 30.0, 18.0, 35.0, 130.0, 40.0, 3),
        (25, 40.0, 22.0, 50.0, 140.0, 50.0, 4),
        (48, None, None, None, 150.0, None, 5),
        (120, 5.0, -10.0, 12.0, 160.0, 70.0, 6),
    ]

    statistics_session.add_all(
        Statistics(
            metadata_id=metadata_id,
            start_ts=(start + timedelta(hours=hour)).timestamp(),
            mean=mean,
            min=minimum,
            max=maximum,
            state=state,
            sum=sum_,
            last_reset_ts=(start + timedelta(hours=reset_offset)).timestamp(),
        )
        for metadata_id in (1, 2)
        for hour, mean, minimum, maximum, state, sum_, reset_offset in samples
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=10),
            {"test:statistic_1", "test:statistic_2"},
            period,
            None,
            types,
        )

    assert baseline.call_count == 1

    actual = statistics._statistics_during_period_with_session(
        hass,
        statistics_session,
        start,
        start + timedelta(days=10),
        {"test:statistic_1", "test:statistic_2"},
        period,
        None,
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
    statistics_session: Session,
    hass: HomeAssistant,
    statistic_ids: set[str] | None,
) -> None:
    """Allow aggregate requests for statistics without a mean."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "temperature",
            StatisticsMeta.unit_of_measurement: "°C",
            StatisticsMeta.has_sum: False,
        }
    )
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 2).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.NONE,
            StatisticsMeta.unit_class: "temperature",
            StatisticsMeta.unit_of_measurement: "°C",
            StatisticsMeta.has_sum: False,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
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
    statistics_session.commit()

    types: set[Literal["max", "mean", "min"]] = {"mean", "min", "max"}

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
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
        statistics_session,
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


async def test_circular_statistics_without_mean_use_fast_path(
    statistics_session: Session,
    hass: HomeAssistant,
) -> None:
    """Use the optimized period query for circular statistics without mean."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.CIRCULAR,
            StatisticsMeta.unit_class: "angle",
            StatisticsMeta.unit_of_measurement: "°",
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=350.0,
                mean_weight=1.0,
                min=340.0,
                max=355.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=10.0,
                mean_weight=1.0,
                min=5.0,
                max=20.0,
            ),
        ]
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        wraps=statistics._get_statistics_period_rows,
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {"test:statistic_1"},
            "day",
            None,
            {"min", "max"},
        )

    optimized.assert_called_once()
    assert result["test:statistic_1"][0]["min"] == 5.0
    assert result["test:statistic_1"][0]["max"] == 355.0


@pytest.mark.parametrize(
    ("unit_class", "unit", "mean_type", "period", "types"),
    [
        pytest.param(
            "power",
            "W",
            StatisticMeanType.ARITHMETIC,
            "5minute",
            {"mean"},
            id="5minute",
        ),
        pytest.param(
            "power",
            "W",
            StatisticMeanType.ARITHMETIC,
            "hour",
            {"mean"},
            id="hour",
        ),
        pytest.param(
            "power",
            "W",
            StatisticMeanType.NONE,
            "day",
            {"mean"},
            id="missing-mean",
        ),
    ],
)
async def test_mean_fallback(
    statistics_session: Session,
    hass: HomeAssistant,
    unit_class: str,
    unit: str,
    mean_type: StatisticMeanType,
    period: Literal["5minute", "hour", "day"],
    types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
) -> None:
    """Fall back for five-minute, hourly and unavailable-mean requests."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.unit_class: unit_class,
            StatisticsMeta.unit_of_measurement: unit,
            StatisticsMeta.mean_type: mean_type,
        }
    )
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    table = StatisticsShortTerm if period == "5minute" else Statistics

    statistics_session.add(
        table(
            metadata_id=1,
            start_ts=start.timestamp(),
            mean=100.0,
            mean_weight=1.0,
            min=50.0,
        )
    )

    statistics_session.commit()
    with patch.object(statistics, "_get_statistics_period_rows") as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(hours=1),
            {"test:statistic_1"},
            period,
            None,
            types,
        )
    optimized.assert_not_called()
    assert result["test:statistic_1"]


async def test_same_unit_aggregate_uses_fast_path(
    statistics_session: Session,
    hass: HomeAssistant,
) -> None:
    """Use the optimized path when the requested unit requires no conversion."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "power",
            StatisticsMeta.unit_of_measurement: "W",
            StatisticsMeta.has_sum: False,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=1000.0,
                min=500.0,
                max=1500.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=3000.0,
                min=2500.0,
                max=3500.0,
            ),
        ]
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        wraps=statistics._get_statistics_period_rows,
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {"test:statistic_1"},
            "day",
            {"power": "W"},
            {"mean", "min", "max"},
        )

    optimized.assert_called_once()

    row = result["test:statistic_1"][0]
    assert row["mean"] == pytest.approx(2000.0)
    assert row["min"] == pytest.approx(500.0)
    assert row["max"] == pytest.approx(3500.0)


@pytest.mark.parametrize(
    "types",
    [
        pytest.param({"mean"}, id="mean"),
        pytest.param({"min"}, id="min"),
        pytest.param({"max"}, id="max"),
        pytest.param({"mean", "min", "max"}, id="all-aggregates"),
        pytest.param({"mean", "sum"}, id="mixed-aggregate-endpoint"),
    ],
)
async def test_unit_converted_aggregates_use_row_based_path(
    statistics_session: Session,
    hass: HomeAssistant,
    types: set[Literal["max", "mean", "min", "sum"]],
) -> None:
    """Use the row-based path when aggregate statistics require unit conversion."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "power",
            StatisticsMeta.unit_of_measurement: "W",
            StatisticsMeta.has_sum: True,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=1000.0,
                min=500.0,
                max=1500.0,
                sum=1000.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=3000.0,
                min=2500.0,
                max=3500.0,
                sum=3000.0,
            ),
        ]
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {"test:statistic_1"},
            "day",
            {"power": "kW"},
            types,
        )

    optimized.assert_not_called()

    row = result["test:statistic_1"][0]
    expected = {
        "mean": 2.0,
        "min": 0.5,
        "max": 3.5,
        "sum": 3.0,
    }

    for stat_type in types:
        assert row[stat_type] == pytest.approx(expected[stat_type])


async def test_state_unit_converted_aggregate_uses_row_based_path(
    statistics_session: Session,
    hass: HomeAssistant,
) -> None:
    """Use the row-based path when the state unit requires conversion."""
    statistic_id = "sensor.test_statistic"

    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.statistic_id: statistic_id,
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "power",
            StatisticsMeta.unit_of_measurement: "W",
            StatisticsMeta.has_sum: False,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=1000.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=3000.0,
            ),
        ]
    )
    statistics_session.commit()

    hass.states.async_set(
        statistic_id,
        "1",
        {EntityStateAttribute.UNIT_OF_MEASUREMENT: "kW"},
    )

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {statistic_id},
            "day",
            None,
            {"mean"},
        )

    optimized.assert_not_called()
    assert result[statistic_id][0]["mean"] == pytest.approx(2.0)


async def test_inverse_unit_conversion_uses_row_based_path(
    statistics_session: Session,
    hass: HomeAssistant,
) -> None:
    """Convert inverse units before reducing statistics."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "energy_distance",
            StatisticsMeta.unit_of_measurement: (
                UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM
            ),
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=10.0,
                min=10.0,
                max=10.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=20.0,
                min=20.0,
                max=20.0,
            ),
        ]
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {"test:statistic_1"},
            "day",
            {"energy_distance": (UnitOfEnergyDistance.KM_PER_KILO_WATT_HOUR)},
            {"mean", "min", "max"},
        )

    optimized.assert_not_called()

    row = result["test:statistic_1"][0]
    assert row["mean"] == pytest.approx(7.5)
    assert row["min"] == pytest.approx(5.0)
    assert row["max"] == pytest.approx(10.0)


async def test_beaufort_unit_conversion_uses_row_based_path(
    statistics_session: Session,
    hass: HomeAssistant,
) -> None:
    """Convert Beaufort values before reducing statistics."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: "speed",
            StatisticsMeta.unit_of_measurement: UnitOfSpeed.METERS_PER_SECOND,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=1.0,
                min=1.0,
                max=1.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=10.0,
                min=10.0,
                max=10.0,
            ),
        ]
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {"test:statistic_1"},
            "day",
            {"speed": UnitOfSpeed.BEAUFORT},
            {"mean", "min", "max"},
        )

    optimized.assert_not_called()

    row = result["test:statistic_1"][0]
    assert row["mean"] == pytest.approx(3.0)
    assert row["min"] == pytest.approx(1.0)
    assert row["max"] == pytest.approx(5.0)


async def test_circular_mean_uses_fast_path(
    statistics_session: Session,
    hass: HomeAssistant,
) -> None:
    """Reduce circular mean statistics in the database."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.CIRCULAR,
            StatisticsMeta.unit_class: "angle",
            StatisticsMeta.unit_of_measurement: "°",
            StatisticsMeta.has_sum: False,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=350.0,
                mean_weight=1.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=20.0,
                mean_weight=1.0,
            ),
        ]
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ) as baseline:
        expected = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {"test:statistic_1"},
            "day",
            None,
            {"mean"},
        )

    baseline.assert_called_once()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        wraps=statistics._get_statistics_period_rows,
    ) as optimized:
        actual = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {"test:statistic_1"},
            "day",
            None,
            {"mean"},
        )

    optimized.assert_called_once()

    assert actual.keys() == expected.keys()
    for statistic_id, rows in expected.items():
        assert len(actual[statistic_id]) == len(rows)
        for actual_row, expected_row in zip(actual[statistic_id], rows, strict=True):
            assert actual_row == pytest.approx(
                expected_row,
                rel=1e-12,
                abs=1e-12,
            )

    assert actual["test:statistic_1"][0]["mean"] == pytest.approx(5.0)


@pytest.mark.parametrize(
    "period",
    [
        pytest.param("day", id="day"),
        pytest.param("week", id="week"),
        pytest.param("month", id="month"),
        pytest.param("year", id="year"),
    ],
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
async def test_mixed_mean_types_use_fast_path(
    statistics_session: Session,
    hass: HomeAssistant,
    period: Literal["day", "week", "month", "year"],
    statistic_ids: set[str] | None,
) -> None:
    """Reduce mixed mean types with separate optimized queries."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: None,
            StatisticsMeta.unit_of_measurement: None,
        }
    )

    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 2).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.CIRCULAR,
            StatisticsMeta.unit_class: None,
            StatisticsMeta.unit_of_measurement: None,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=10.0,
                mean_weight=1.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=20.0,
                mean_weight=1.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=start.timestamp(),
                mean=350.0,
                mean_weight=1.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=20.0,
                mean_weight=1.0,
            ),
        ]
    )

    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        wraps=statistics._get_statistics_period_rows,
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            statistic_ids,
            period,
            None,
            {"mean"},
        )

    assert optimized.call_count == 2
    assert result["test:statistic_1"][0]["mean"] == pytest.approx(15.0)
    assert result["test:statistic_2"][0]["mean"] == pytest.approx(5.0)


async def test_circular_mean_with_missing_weight_matches_legacy(
    statistics_session: Session,
    hass: HomeAssistant,
) -> None:
    """Treat missing circular mean weights as zero."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.CIRCULAR,
            StatisticsMeta.unit_class: None,
            StatisticsMeta.unit_of_measurement: None,
            StatisticsMeta.has_sum: False,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=350.0,
                mean_weight=None,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=20.0,
                mean_weight=None,
            ),
        ]
    )
    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        side_effect=_unoptimized_statistics,
    ):
        expected = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            {"test:statistic_1"},
            "day",
            None,
            {"mean"},
        )

    actual = statistics._statistics_during_period_with_session(
        hass,
        statistics_session,
        start,
        start + timedelta(days=1),
        {"test:statistic_1"},
        "day",
        None,
        {"mean"},
    )

    assert actual == expected


@pytest.mark.parametrize(
    "statistic_ids",
    [
        pytest.param(None, id="all-statistics"),
        pytest.param(
            {
                "test:statistic_1",
                "test:statistic_2",
                "test:statistic_3",
            },
            id="selected-statistics",
        ),
    ],
)
async def test_mixed_mean_types_include_statistics_without_mean(
    statistics_session: Session,
    hass: HomeAssistant,
    statistic_ids: set[str] | None,
) -> None:
    """Keep statistics without a mean in mixed optimized queries."""
    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 1).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.ARITHMETIC,
            StatisticsMeta.unit_class: None,
            StatisticsMeta.unit_of_measurement: None,
        }
    )

    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 2).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.CIRCULAR,
            StatisticsMeta.unit_class: None,
            StatisticsMeta.unit_of_measurement: None,
        }
    )

    statistics_session.query(StatisticsMeta).filter(StatisticsMeta.id == 3).update(
        {
            StatisticsMeta.mean_type: StatisticMeanType.NONE,
            StatisticsMeta.unit_class: None,
            StatisticsMeta.unit_of_measurement: None,
        }
    )

    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)

    statistics_session.add_all(
        [
            Statistics(
                metadata_id=1,
                start_ts=start.timestamp(),
                mean=10.0,
                mean_weight=1.0,
                min=5.0,
                max=15.0,
            ),
            Statistics(
                metadata_id=1,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=20.0,
                mean_weight=1.0,
                min=8.0,
                max=25.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=start.timestamp(),
                mean=350.0,
                mean_weight=1.0,
                min=340.0,
                max=355.0,
            ),
            Statistics(
                metadata_id=2,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=20.0,
                mean_weight=1.0,
                min=10.0,
                max=30.0,
            ),
            Statistics(
                metadata_id=3,
                start_ts=start.timestamp(),
                mean=None,
                min=2.0,
                max=12.0,
            ),
            Statistics(
                metadata_id=3,
                start_ts=(start + timedelta(hours=1)).timestamp(),
                mean=None,
                min=4.0,
                max=18.0,
            ),
        ]
    )

    statistics_session.commit()

    with patch.object(
        statistics,
        "_get_statistics_period_rows",
        wraps=statistics._get_statistics_period_rows,
    ) as optimized:
        result = statistics._statistics_during_period_with_session(
            hass,
            statistics_session,
            start,
            start + timedelta(days=1),
            statistic_ids,
            "day",
            None,
            {"mean", "min", "max"},
        )

    assert optimized.call_count == 2

    assert result["test:statistic_1"][0]["mean"] == pytest.approx(15.0)
    assert result["test:statistic_1"][0]["min"] == 5.0
    assert result["test:statistic_1"][0]["max"] == 25.0

    assert result["test:statistic_2"][0]["mean"] == pytest.approx(5.0)
    assert result["test:statistic_2"][0]["min"] == 10.0
    assert result["test:statistic_2"][0]["max"] == 355.0

    assert result["test:statistic_3"][0]["mean"] is None
    assert result["test:statistic_3"][0]["min"] == 2.0
    assert result["test:statistic_3"][0]["max"] == 18.0
