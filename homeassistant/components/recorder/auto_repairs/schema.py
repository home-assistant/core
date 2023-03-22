"""Schema repairs."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import contextlib
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.session import Session

from homeassistant.util import dt as dt_util

from ..const import SupportedDialect
from ..util import session_scope

if TYPE_CHECKING:
    from .. import Recorder

_LOGGER = logging.getLogger(__name__)

MYSQL_ERR_INCORRECT_STRING_VALUE = 1366

# This name can't be represented unless 4-byte UTF-8 unicode is supported
UTF8_NAME = "𓆚𓃗"

# This number can't be accurately represented as a 32-bit float
PRECISE_NUMBER = 1.000000000000001


def _get_future_year() -> int:
    """Get a year in the future."""
    return datetime.now().year + 1


def get_precise_datetime() -> datetime:
    """Get a datetime with a precise microsecond.

    This time can't be accurately represented unless datetimes have µs precision
    """
    future_year = _get_future_year()
    return datetime(future_year, 10, 6, microsecond=1, tzinfo=dt_util.UTC)


def validate_table_schema_supports_utf8(
    instance: Recorder,
    table_object: type[DeclarativeBase],
    columns: tuple[str, ...],
    session_maker: Callable[[], Session],
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()

    # Lack of full utf8 support is only an issue for MySQL / MariaDB
    if instance.dialect_name != SupportedDialect.MYSQL:
        return schema_errors

    # Try inserting some data which needs utf8mb4 support
    try:
        # Mark the session as read_only to ensure that the test data is not committed
        # to the database and we always rollback when the scope is exited
        with session_scope(session=session_maker(), read_only=True) as session:
            db_object = table_object(**{column: UTF8_NAME for column in columns})
            table = table_object.__tablename__
            session.add(db_object)
            try:
                session.flush()
            except OperationalError as err:
                if err.orig and err.orig.args[0] == MYSQL_ERR_INCORRECT_STRING_VALUE:
                    _LOGGER.debug(
                        "Database %s statistics_meta does not support 4-byte UTF-8",
                        table,
                    )
                    schema_errors.add(f"{table}.4-byte UTF-8")
                    session.rollback()
                else:
                    raise
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception("Error when validating DB schema: %s", exc)
    return schema_errors


def validate_db_schema_precision(
    instance: Recorder,
    table_object: type[DeclarativeBase],
    columns: tuple[str, ...],
    session_maker: Callable[[], Session],
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    # Wrong precision is only an issue for MySQL / MariaDB / PostgreSQL
    if instance.dialect_name not in (
        SupportedDialect.MYSQL,
        SupportedDialect.POSTGRESQL,
    ):
        return schema_errors

    precise_time_ts = get_precise_datetime().timestamp()

    try:
        # Mark the session as read_only to ensure that the test data is not committed
        # to the database and we always rollback when the scope is exited
        with session_scope(session=session_maker(), read_only=True) as session:
            db_object = table_object(**{column: precise_time_ts for column in columns})
            table = table_object.__tablename__
            session.add(db_object)
            session.flush()
            session.refresh(db_object)
            check_columns(
                schema_errors=schema_errors,
                stored={column: getattr(db_object, column) for column in columns},
                expected={column: precise_time_ts for column in columns},
                columns=columns,
                table_name=table,
                supports="µs precision",
            )
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception("Error when validating DB schema: %s", exc)

    return schema_errors


def check_columns(
    schema_errors: set[str],
    stored: Mapping,
    expected: Mapping,
    columns: tuple[str, ...],
    table_name: str,
    supports: str,
) -> None:
    """Check that the columns in the table support the given feature.

    Errors are logged and added to the schema_errors set.
    """
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


def correct_table_character_set_and_collation(
    table: str,
    session_maker: Callable[[], Session],
) -> None:
    """Correct issues detected by validate_db_schema."""
    # Attempt to convert the table to utf8mb4
    _LOGGER.warning(
        "Updating character set and collation of table %s to utf8mb4. "
        "Note: this can take several minutes on large databases and slow "
        "computers. Please be patient!",
        table,
    )
    with contextlib.suppress(SQLAlchemyError), session_scope(
        session=session_maker()
    ) as session:
        connection = session.connection()
        connection.execute(
            # Using LOCK=EXCLUSIVE to prevent the database from corrupting
            # https://github.com/home-assistant/core/issues/56104
            text(
                f"ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4"
                " COLLATE utf8mb4_unicode_ci, LOCK=EXCLUSIVE"
            )
        )
