"""States schema repairs."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import Session

from homeassistant.core import HomeAssistant

from ...db_schema import States
from ..schema import (
    correct_table_character_set_and_collation,
    validate_db_schema_precision,
    validate_table_schema_supports_utf8,
)

if TYPE_CHECKING:
    from ... import Recorder

_LOGGER = logging.getLogger(__name__)


def validate_db_schema(
    hass: HomeAssistant, instance: Recorder, session_maker: Callable[[], Session]
) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    schema_errors |= validate_table_schema_supports_utf8(
        instance, States, ("state",), session_maker
    )
    schema_errors |= validate_db_schema_precision(
        instance, States, ("last_updated_ts", "last_changed_ts"), session_maker
    )
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
