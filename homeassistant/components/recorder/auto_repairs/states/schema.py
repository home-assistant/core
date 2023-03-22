"""States schema repairs."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import Session

from homeassistant.core import HomeAssistant

from ...const import SupportedDialect
from ...db_schema import States
from ...util import session_scope
from ..schema import (
    UTF8_NAME,
    check_columns,
    correct_table_character_set_and_collation,
    get_precise_datetime,
    validate_table_schema_supports_utf8,
)

if TYPE_CHECKING:
    from ... import Recorder

_LOGGER = logging.getLogger(__name__)


def _validate_db_schema_utf8(
    instance: Recorder, session_maker: Callable[[], Session]
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    state = States(state=UTF8_NAME)
    return validate_table_schema_supports_utf8(
        instance=instance,
        table_object=state,
        session_maker=session_maker,
    )


def _validate_db_schema_precision(
    instance: Recorder, session_maker: Callable[[], Session]
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
            state = States(
                last_changed_ts=precise_time_ts,
                last_updated_ts=precise_time_ts,
            )
            session.flush()
            session.refresh(state)
            check_columns(
                schema_errors=schema_errors,
                stored={
                    "last_changed_ts": state.last_changed_ts,
                    "last_updated_ts": state.last_updated_ts,
                },
                expected={
                    "last_changed_ts": precise_time_ts,
                    "last_updated_ts": precise_time_ts,
                },
                columns=("last_changed_ts", "last_updated_ts"),
                table_name="states",
                supports="µs precision",
            )
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.exception("Error when validating DB schema: %s", exc)

    return schema_errors


def validate_db_schema(
    hass: HomeAssistant, instance: Recorder, session_maker: Callable[[], Session]
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    schema_errors |= _validate_db_schema_utf8(instance, session_maker)
    schema_errors |= _validate_db_schema_precision(instance, session_maker)
    if schema_errors:
        _LOGGER.debug(
            "Detected states schema errors: %s", ", ".join(sorted(schema_errors))
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

    if "states.4-byte UTF-8" in schema_errors:
        correct_table_character_set_and_collation("states", session_maker)

    if "states.µs precision" in schema_errors:
        # Attempt to convert timestamp columns to µs precision
        _modify_columns(
            session_maker,
            engine,
            "states",
            [
                "last_updated_ts DOUBLE PRECISION",
                "last_changed_ts DOUBLE PRECISION",
            ],
        )
