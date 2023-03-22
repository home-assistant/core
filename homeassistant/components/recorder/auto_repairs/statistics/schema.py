"""Statistics schema repairs."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import Session

from homeassistant.core import HomeAssistant

from ...const import DOMAIN, SupportedDialect
from ...db_schema import Statistics, StatisticsMeta, StatisticsShortTerm
from ...models import StatisticData, StatisticMetaData, datetime_to_timestamp_or_none
from ...statistics import (
    _import_statistics_with_session,
    _statistics_during_period_with_session,
)
from ...util import session_scope
from ..schema import (
    PRECISE_NUMBER,
    check_columns,
    correct_table_character_set_and_collation,
    get_precise_datetime,
    validate_table_schema_supports_utf8,
)

if TYPE_CHECKING:
    from ... import Recorder

_LOGGER = logging.getLogger(__name__)

STATISTIC_ID = f"{DOMAIN}.db_test"


def _validate_db_schema(
    hass: HomeAssistant, instance: Recorder, session_maker: Callable[[], Session]
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    statistics_meta_manager = instance.statistics_meta_manager

    # Wrong precision is only an issue for MySQL / MariaDB / PostgreSQL
    if instance.dialect_name not in (
        SupportedDialect.MYSQL,
        SupportedDialect.POSTGRESQL,
    ):
        return schema_errors

    # This time can't be accurately represented unless datetimes have µs precision
    #
    # We want to insert statistics for a time in the future, in case they
    # have conflicting metadata_id's with existing statistics that were
    # never cleaned up. By inserting in the future, we can be sure that
    # that by selecting the last inserted row, we will get the one we
    # just inserted.
    #
    precise_time = get_precise_datetime()
    start_time = precise_time.replace(microsecond=0)

    metadata: StatisticMetaData = {
        "has_mean": True,
        "has_sum": True,
        "name": None,
        "source": DOMAIN,
        "statistic_id": STATISTIC_ID,
        "unit_of_measurement": None,
    }
    statistics: StatisticData = {
        "last_reset": precise_time,
        "max": PRECISE_NUMBER,
        "mean": PRECISE_NUMBER,
        "min": PRECISE_NUMBER,
        "start": precise_time,
        "state": PRECISE_NUMBER,
        "sum": PRECISE_NUMBER,
    }

    # Insert / adjust a test statistics row in each of the tables
    tables: tuple[type[Statistics | StatisticsShortTerm], ...] = (
        Statistics,
        StatisticsShortTerm,
    )
    try:
        # Mark the session as read_only to ensure that the test data is not committed
        # to the database and we always rollback when the scope is exited
        with session_scope(session=session_maker(), read_only=True) as session:
            for table in tables:
                _import_statistics_with_session(
                    instance, session, metadata, (statistics,), table
                )
                stored_statistics = _statistics_during_period_with_session(
                    hass,
                    session,
                    start_time,
                    None,
                    {STATISTIC_ID},
                    "hour" if table == Statistics else "5minute",
                    None,
                    {"last_reset", "max", "mean", "min", "state", "sum"},
                )
                if not (stored_statistic := stored_statistics.get(STATISTIC_ID)):
                    _LOGGER.warning(
                        "Schema validation failed for table: %s", table.__tablename__
                    )
                    continue

                # We want to look at the last inserted row to make sure there
                # is not previous garbage data in the table that would cause
                # the test to produce an incorrect result. To achieve this,
                # we inserted a row in the future, and now we select the last
                # inserted row back.
                last_stored_statistic = stored_statistic[-1]
                check_columns(
                    schema_errors=schema_errors,
                    stored=last_stored_statistic,
                    expected=statistics,
                    columns=("max", "mean", "min", "state", "sum"),
                    table_name=table.__tablename__,
                    supports="double precision",
                )
                assert statistics["last_reset"]
                check_columns(
                    schema_errors=schema_errors,
                    stored=last_stored_statistic,
                    expected={
                        "last_reset": datetime_to_timestamp_or_none(
                            statistics["last_reset"]
                        ),
                        "start": datetime_to_timestamp_or_none(statistics["start"]),
                    },
                    columns=("start", "last_reset"),
                    table_name=table.__tablename__,
                    supports="µs precision",
                )
            statistics_meta_manager.delete(session, statistic_ids=[STATISTIC_ID])
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception("Error when validating DB schema: %s", exc)

    return schema_errors


def validate_db_schema(
    hass: HomeAssistant, instance: Recorder, session_maker: Callable[[], Session]
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    schema_errors |= validate_table_schema_supports_utf8(
        instance, StatisticsMeta, ("statistic_id",), session_maker
    )
    schema_errors |= _validate_db_schema(hass, instance, session_maker)
    if schema_errors:
        _LOGGER.debug(
            "Detected statistics schema errors: %s", ", ".join(sorted(schema_errors))
        )
    return schema_errors


def correct_db_schema(
    instance: Recorder,
    engine: Engine,
    session_maker: Callable[[], Session],
    schema_errors: set[str],
) -> None:
    """Correct issues detected by validate_db_schema."""
    from ...migration import _modify_columns  # pylint: disable=import-outside-toplevel

    if "statistics_meta.4-byte UTF-8" in schema_errors:
        correct_table_character_set_and_collation("statistics_meta", session_maker)

    tables: tuple[type[Statistics | StatisticsShortTerm], ...] = (
        Statistics,
        StatisticsShortTerm,
    )
    for table in tables:
        if f"{table.__tablename__}.double precision" in schema_errors:
            # Attempt to convert float columns to double precision
            _modify_columns(
                session_maker,
                engine,
                table.__tablename__,
                [
                    "mean DOUBLE PRECISION",
                    "min DOUBLE PRECISION",
                    "max DOUBLE PRECISION",
                    "state DOUBLE PRECISION",
                    "sum DOUBLE PRECISION",
                ],
            )
        if f"{table.__tablename__}.µs precision" in schema_errors:
            # Attempt to convert timestamp columns to µs precision
            _modify_columns(
                session_maker,
                engine,
                table.__tablename__,
                [
                    "last_reset_ts DOUBLE PRECISION",
                    "start_ts DOUBLE PRECISION",
                ],
            )
