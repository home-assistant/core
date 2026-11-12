"""Constants for the Statistics integration."""

from enum import StrEnum


class StatisticsEntityStateAttribute(StrEnum):
    """State attributes for statistics entities."""

    AGE_COVERAGE_RATIO = "age_coverage_ratio"
    BUFFER_USAGE_RATIO = "buffer_usage_ratio"
    SOURCE_VALUE_VALID = "source_value_valid"
