"""Statistics schema repairs."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import contextlib
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm.session import Session

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ...const import DOMAIN, SupportedDialect
from ...db_schema import Statistics, StatisticsShortTerm
from ...models import StatisticData, StatisticMetaData, datetime_to_timestamp_or_none
from ...statistics import (
    _import_statistics_with_session,
    _statistics_during_period_with_session,
)
from ...util import session_scope

if TYPE_CHECKING:
    from ... import Recorder

_LOGGER = logging.getLogger(__name__)


def _validate_db_schema_utf8(
    instance: Recorder, session_maker: Callable[[], Session]
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()

    # Lack of full utf8 support is only an issue for MySQL / MariaDB
    if instance.dialect_name != SupportedDialect.MYSQL:
        return schema_errors

    # This name can't be represented unless 4-byte UTF-8 unicode is supported
    utf8_name = "𓆚𓃗"
    statistic_id = f"{DOMAIN}.db_test"

    metadata: StatisticMetaData = {
        "has_mean": True,
        "has_sum": True,
        "name": utf8_name,
        "source": DOMAIN,
        "statistic_id": statistic_id,
        "unit_of_measurement": None,
    }
    statistics_meta_manager = instance.statistics_meta_manager

    # Try inserting some metadata which needs utf8mb4 support
    try:
        # Mark the session as read_only to ensure that the test data is not committed
        # to the database and we always rollback when the scope is exited
        with session_scope(session=session_maker(), read_only=True) as session:
            old_metadata_dict = statistics_meta_manager.get_many(
                session, statistic_ids={statistic_id}
            )
            try:
                statistics_meta_manager.update_or_add(
                    session, metadata, old_metadata_dict
                )
                statistics_meta_manager.delete(session, statistic_ids=[statistic_id])
            except OperationalError as err:
                if err.orig and err.orig.args[0] == 1366:
                    _LOGGER.debug(
                        "Database table statistics_meta does not support 4-byte UTF-8"
                    )
                    schema_errors.add("statistics_meta.4-byte UTF-8")
                    session.rollback()
                else:
                    raise
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception("Error when validating DB schema: %s", exc)
    return schema_errors


def _get_future_year() -> int:
    """Get a year in the future."""
    return datetime.now().year + 1


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

    # This number can't be accurately represented as a 32-bit float
    precise_number = 1.000000000000001
    # This time can't be accurately represented unless datetimes have µs precision
    #
    # We want to insert statistics for a time in the future, in case they
    # have conflicting metadata_id's with existing statistics that were
    # never cleaned up. By inserting in the future, we can be sure that
    # that by selecting the last inserted row, we will get the one we
    # just inserted.
    #
    future_year = _get_future_year()
    precise_time = datetime(future_year, 10, 6, microsecond=1, tzinfo=dt_util.UTC)
    start_time = datetime(future_year, 10, 6, tzinfo=dt_util.UTC)
    statistic_id = f"{DOMAIN}.db_test"

    metadata: StatisticMetaData = {
        "has_mean": True,
        "has_sum": True,
        "name": None,
        "source": DOMAIN,
        "statistic_id": statistic_id,
        "unit_of_measurement": None,
    }
    statistics: StatisticData = {
        "last_reset": precise_time,
        "max": precise_number,
        "mean": precise_number,
        "min": precise_number,
        "start": precise_time,
        "state": precise_number,
        "sum": precise_number,
    }

    def check_columns(
        schema_errors: set[str],
        stored: Mapping,
        expected: Mapping,
        columns: tuple[str, ...],
        table_name: str,
        supports: str,
    ) -> None:
        for column in columns:
            if stored[column] != expected[column]:
                schema_errors.add(f"{table_name}.{supports}")
                _LOGGER.error(
                    "Column %s in database table %s does not support %s (stored=%s != expected=%s)",
                    column,
                    table_name,
                    supports,
                    stored[column],
                    expected[column],
                )

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
                    {statistic_id},
                    "hour" if table == Statistics else "5minute",
                    None,
                    {"last_reset", "max", "mean", "min", "state", "sum"},
                )
                if not (stored_statistic := stored_statistics.get(statistic_id)):
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
                    schema_errors,
                    last_stored_statistic,
                    statistics,
                    ("max", "mean", "min", "state", "sum"),
                    table.__tablename__,
                    "double precision",
                )
                assert statistics["last_reset"]
                check_columns(
                    schema_errors,
                    last_stored_statistic,
                    {
                        "last_reset": datetime_to_timestamp_or_none(
                            statistics["last_reset"]
                        ),
                        "start": datetime_to_timestamp_or_none(statistics["start"]),
                    },
                    ("start", "last_reset"),
                    table.__tablename__,
                    "µs precision",
                )
            statistics_meta_manager.delete(session, statistic_ids=[statistic_id])
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception("Error when validating DB schema: %s", exc)

    return schema_errors


def validate_db_schema(
    hass: HomeAssistant, instance: Recorder, session_maker: Callable[[], Session]
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    schema_errors |= _validate_db_schema_utf8(instance, session_maker)
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
        # Attempt to convert the table to utf8mb4
        _LOGGER.warning(
            (
                "Updating character set and collation of table %s to utf8mb4. "
                "Note: this can take several minutes on large databases and slow "
                "computers. Please be patient!"
            ),
            "statistics_meta",
        )
        with contextlib.suppress(SQLAlchemyError), session_scope(
            session=session_maker()
        ) as session:
            connection = session.connection()
            connection.execute(
                # Using LOCK=EXCLUSIVE to prevent the database from corrupting
                # https://github.com/home-assistant/core/issues/56104
                text(
                    "ALTER TABLE statistics_meta CONVERT TO CHARACTER SET utf8mb4"
                    " COLLATE utf8mb4_unicode_ci, LOCK=EXCLUSIVE"
                )
            )

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
