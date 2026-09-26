"""Tests for selecting calendar-period statistics endpoints in SQL."""

from collections.abc import Callable, Generator, Sequence
from datetime import datetime, timedelta
from typing import Literal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine.row import Row
from sqlalchemy.orm import Session

from homeassistant.components.recorder import statistics
from homeassistant.components.recorder.db_schema import Statistics, StatisticsMeta
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.util import execute_stmt_lambda_element
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import async_wait_recording_done


@pytest.fixture
def endpoint_session() -> Generator[Session]:
    """Create a small database with the production statistics schema."""
    engine = create_engine("sqlite://")
    StatisticsMeta.__table__.create(engine)
    Statistics.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.mark.parametrize(("days", "queries"), [(399, 1), (400, 1), (401, 2), (801, 3)])
def test_endpoint_query_batches(
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
        rows = statistics._get_statistics_period_endpoints(
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


def test_endpoint_parameter_budget(endpoint_session: Session) -> None:
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
        rows = statistics._get_statistics_period_endpoints(
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
        assert len(compiled.positiontup) <= 10


def _unreduced_statistics(
    session: Session,
    start_time: datetime,
    end_time: datetime | None,
    metadata_ids: list[int] | None,
    period_start_end: Callable[[float], tuple[float, float]],
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
    max_bind_vars: int,
) -> Sequence[Row]:
    """Execute the original query to compare the complete public result."""
    return execute_stmt_lambda_element(
        session,
        statistics._generate_statistics_during_period_stmt(
            start_time, end_time, metadata_ids, Statistics, types
        ),
        orm_rows=False,
    )


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.freeze_time("2024-10-01 00:00:00+00:00")
@pytest.mark.parametrize("timezone", ["UTC", "Europe/Amsterdam", "America/Havana"])
@pytest.mark.parametrize("period", ["day", "week", "month", "year"])
@pytest.mark.parametrize(
    "types",
    [{"sum"}, {"change"}, {"sum", "change", "state", "last_reset"}],
)
@pytest.mark.parametrize(
    "end_time", [None, datetime(2024, 11, 3, 3, tzinfo=dt_util.UTC)]
)
async def test_endpoint_results_match_original(
    hass: HomeAssistant,
    timezone: str,
    period: Literal["day", "week", "month", "year"],
    types: set[Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]],
    end_time: datetime | None,
) -> None:
    """Preserve resets, corrections, missing data, conversion and DST semantics."""
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
        "_get_statistics_period_endpoints",
        side_effect=_unreduced_statistics,
    ) as baseline:
        expected = statistics.statistics_during_period(
            hass, start, end_time, None, period, {"energy": "Wh"}, types
        )
    assert baseline.call_count == 1
    actual = statistics.statistics_during_period(
        hass, start, end_time, None, period, {"energy": "Wh"}, types
    )
    assert expected
    assert actual == expected
