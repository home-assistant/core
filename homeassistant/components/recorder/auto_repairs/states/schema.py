"""States schema repairs."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ...db_schema import DOUBLE_PRECISION_TYPE_SQL, States
from ..schema import (
    correct_db_schema_utf8_and_precision,
    validate_db_schema_utf8_and_precision,
)

if TYPE_CHECKING:
    from ... import Recorder

PRECISION_COLUMN_TYPES = {
    "last_updated_ts": DOUBLE_PRECISION_TYPE_SQL,
    "last_changed_ts": DOUBLE_PRECISION_TYPE_SQL,
}
UTF8_COLUMN_TYPES = ("state",)


def validate_db_schema(instance: Recorder) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    return validate_db_schema_utf8_and_precision(
        instance, States, UTF8_COLUMN_TYPES, PRECISION_COLUMN_TYPES
    )


def correct_db_schema(
    instance: Recorder,
    schema_errors: set[str],
) -> None:
    """Correct issues detected by validate_db_schema."""
    return correct_db_schema_utf8_and_precision(
        instance, States, PRECISION_COLUMN_TYPES, schema_errors
    )
