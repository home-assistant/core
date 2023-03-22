"""States schema repairs."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ...db_schema import States
from ..schema import (
    correct_db_schema_utf8_and_precision,
    validate_db_schema_utf8_and_precision,
)

if TYPE_CHECKING:
    from ... import Recorder


def validate_db_schema(instance: Recorder) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    return validate_db_schema_utf8_and_precision(instance, States, ("state",))


def correct_db_schema(
    instance: Recorder,
    schema_errors: set[str],
) -> None:
    """Correct issues detected by validate_db_schema."""
    correct_db_schema_utf8_and_precision(instance, States, schema_errors)
