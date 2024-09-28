"""Statistics schema repairs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...db_schema import Statistics, StatisticsMeta, StatisticsShortTerm
from ..schema import (
    correct_db_schema_precision,
    correct_db_schema_utf8,
    validate_db_schema_precision,
    validate_table_schema_has_correct_collation,
    validate_table_schema_supports_utf8,
)

if TYPE_CHECKING:
    from ... import Recorder

_LOGGER = logging.getLogger(__name__)


def validate_db_schema(instance: Recorder) -> set[str]:
    """Do some basic checks for common schema errors caused by manual migration."""
    schema_errors: set[str] = set()
    schema_errors |= validate_table_schema_supports_utf8(
        instance, StatisticsMeta, (StatisticsMeta.statistic_id,)
    )
    for table in (Statistics, StatisticsShortTerm):
        schema_errors |= validate_db_schema_precision(instance, table)
        schema_errors |= validate_table_schema_has_correct_collation(instance, table)
    if schema_errors:
        _LOGGER.debug(
            "Detected statistics schema errors: %s", ", ".join(sorted(schema_errors))
        )
    return schema_errors


def correct_db_schema(
    instance: Recorder,
    schema_errors: set[str],
) -> None:
    """Correct issues detected by validate_db_schema."""
    correct_db_schema_utf8(instance, StatisticsMeta, schema_errors)
    for table in (Statistics, StatisticsShortTerm):
        correct_db_schema_precision(instance, table, schema_errors)
        correct_db_schema_utf8(instance, table, schema_errors)
