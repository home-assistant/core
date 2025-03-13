"""Schema repairs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import TYPE_CHECKING

from sqlalchemy import MetaData, Table
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.attributes import InstrumentedAttribute

from ..const import SupportedDialect
from ..db_schema import DOUBLE_PRECISION_TYPE_SQL, DOUBLE_TYPE
from ..util import session_scope

if TYPE_CHECKING:
    from .. import Recorder

_LOGGER = logging.getLogger(__name__)

MYSQL_ERR_INCORRECT_STRING_VALUE = 1366

# This name can't be represented unless 4-byte UTF-8 unicode is supported
UTF8_NAME = "𓆚𓃗"

# This number can't be accurately represented as a 32-bit float
PRECISE_NUMBER = 1.000000000000001


def _get_precision_column_types(
    table_object: type[DeclarativeBase],
) -> list[str]:
    """Get the column names for the columns that need to be checked for precision."""
    return [
        column.key
        for column in table_object.__table__.columns
        if column.type is DOUBLE_TYPE
    ]


def validate_table_schema_supports_utf8(
    instance: Recorder,
    table_object: type[DeclarativeBase],
    columns: tuple[InstrumentedAttribute, ...],
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    # Lack of full utf8 support is only an issue for MySQL / MariaDB
    if instance.dialect_name != SupportedDialect.MYSQL:
        return schema_errors

    try:
        schema_errors = _validate_table_schema_supports_utf8(
            instance, table_object, columns
        )
    except Exception:
        _LOGGER.exception("Error when validating DB schema")

    _log_schema_errors(table_object, schema_errors)
    return schema_errors


def validate_table_schema_has_correct_collation(
    instance: Recorder,
    table_object: type[DeclarativeBase],
) -> set[str]:
    """Verify the table has the correct collation."""
    schema_errors: set[str] = set()
    # Lack of full utf8 support is only an issue for MySQL / MariaDB
    if instance.dialect_name != SupportedDialect.MYSQL:
        return schema_errors

    try:
        schema_errors = _validate_table_schema_has_correct_collation(
            instance, table_object
        )
    except Exception:
        _LOGGER.exception("Error when validating DB schema")

    _log_schema_errors(table_object, schema_errors)
    return schema_errors


def _validate_table_schema_has_correct_collation(
    instance: Recorder,
    table_object: type[DeclarativeBase],
) -> set[str]:
    """Ensure the table has the correct collation to avoid union errors with mixed collations."""
    schema_errors: set[str] = set()
    # Mark the session as read_only to ensure that the test data is not committed
    # to the database and we always rollback when the scope is exited
    with session_scope(session=instance.get_session(), read_only=True) as session:
        table = table_object.__tablename__
        metadata_obj = MetaData()
        reflected_table = Table(table, metadata_obj, autoload_with=instance.engine)
        connection = session.connection()
        dialect_kwargs = reflected_table.dialect_kwargs
        # Check if the table has a collation set, if its not set than its
        # using the server default collation for the database

        collate = (
            dialect_kwargs.get("mysql_collate")
            or dialect_kwargs.get("mariadb_collate")
            or connection.dialect._fetch_setting(connection, "collation_server")  # type: ignore[attr-defined]  # noqa: SLF001
        )
        if collate and collate != "utf8mb4_unicode_ci":
            _LOGGER.debug(
                "Database %s collation is not utf8mb4_unicode_ci",
                table,
            )
            schema_errors.add(f"{table}.utf8mb4_unicode_ci")
    return schema_errors


def _validate_table_schema_supports_utf8(
    instance: Recorder,
    table_object: type[DeclarativeBase],
    columns: tuple[InstrumentedAttribute, ...],
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    # Mark the session as read_only to ensure that the test data is not committed
    # to the database and we always rollback when the scope is exited
    with session_scope(session=instance.get_session(), read_only=True) as session:
        db_object = table_object(**{column.key: UTF8_NAME for column in columns})
        table = table_object.__tablename__
        # Try inserting some data which needs utf8mb4 support
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
                return schema_errors
            raise
        finally:
            session.rollback()
    return schema_errors


def validate_db_schema_precision(
    instance: Recorder,
    table_object: type[DeclarativeBase],
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    # Wrong precision is only an issue for MySQL / MariaDB / PostgreSQL
    if instance.dialect_name not in (
        SupportedDialect.MYSQL,
        SupportedDialect.POSTGRESQL,
    ):
        return schema_errors
    try:
        schema_errors = _validate_db_schema_precision(instance, table_object)
    except Exception:
        _LOGGER.exception("Error when validating DB schema")

    _log_schema_errors(table_object, schema_errors)
    return schema_errors


def _validate_db_schema_precision(
    instance: Recorder,
    table_object: type[DeclarativeBase],
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    columns = _get_precision_column_types(table_object)
    # Mark the session as read_only to ensure that the test data is not committed
    # to the database and we always rollback when the scope is exited
    with session_scope(session=instance.get_session(), read_only=True) as session:
        db_object = table_object(**dict.fromkeys(columns, PRECISE_NUMBER))
        table = table_object.__tablename__
        try:
            session.add(db_object)
            session.flush()
            session.refresh(db_object)
            _check_columns(
                schema_errors=schema_errors,
                stored={column: getattr(db_object, column) for column in columns},
                expected=dict.fromkeys(columns, PRECISE_NUMBER),
                columns=columns,
                table_name=table,
                supports="double precision",
            )
        finally:
            session.rollback()
    return schema_errors


def _log_schema_errors(
    table_object: type[DeclarativeBase], schema_errors: set[str]
) -> None:
    """Log schema errors."""
    if not schema_errors:
        return
    _LOGGER.debug(
        "Detected %s schema errors: %s",
        table_object.__tablename__,
        ", ".join(sorted(schema_errors)),
    )


def _check_columns(
    schema_errors: set[str],
    stored: Mapping,
    expected: Mapping,
    columns: Iterable[str],
    table_name: str,
    supports: str,
) -> None:
    """Check that the columns in the table support the given feature.

    Errors are logged and added to the schema_errors set.
    """
    for column in columns:
        if stored[column] == expected[column]:
            continue
        schema_errors.add(f"{table_name}.{supports}")
        _LOGGER.error(
            "Column %s in database table %s does not support %s (stored=%s != expected=%s)",
            column,
            table_name,
            supports,
            stored[column],
            expected[column],
        )


def correct_db_schema_utf8(
    instance: Recorder, table_object: type[DeclarativeBase], schema_errors: set[str]
) -> None:
    """Correct utf8 issues detected by validate_db_schema."""
    table_name = table_object.__tablename__
    if (
        f"{table_name}.4-byte UTF-8" in schema_errors
        or f"{table_name}.utf8mb4_unicode_ci" in schema_errors
    ):
        from ..migration import (  # pylint: disable=import-outside-toplevel
            _correct_table_character_set_and_collation,
        )

        _correct_table_character_set_and_collation(table_name, instance.get_session)


def correct_db_schema_precision(
    instance: Recorder,
    table_object: type[DeclarativeBase],
    schema_errors: set[str],
) -> None:
    """Correct precision issues detected by validate_db_schema."""
    table_name = table_object.__tablename__

    if f"{table_name}.double precision" in schema_errors:
        from ..migration import (  # pylint: disable=import-outside-toplevel
            _modify_columns,
        )

        precision_columns = _get_precision_column_types(table_object)
        # Attempt to convert timestamp columns to µs precision
        session_maker = instance.get_session
        engine = instance.engine
        assert engine is not None, "Engine should be set"
        _modify_columns(
            session_maker,
            engine,
            table_name,
            [f"{column} {DOUBLE_PRECISION_TYPE_SQL}" for column in precision_columns],
        )
