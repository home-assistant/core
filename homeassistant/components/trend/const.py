"""Constant values for Trend integration."""

from enum import StrEnum

DOMAIN = "trend"

CONF_INVERT = "invert"
CONF_MAX_SAMPLES = "max_samples"
CONF_MIN_GRADIENT = "min_gradient"
CONF_SAMPLE_DURATION = "sample_duration"
CONF_MIN_SAMPLES = "min_samples"

DEFAULT_MAX_SAMPLES = 2
DEFAULT_MIN_SAMPLES = 2
DEFAULT_MIN_GRADIENT = 0.0
DEFAULT_SAMPLE_DURATION = 0


class TrendEntityStateAttribute(StrEnum):
    """State attributes for trend entities."""

    ENTITY_ID = "entity_id"
    GRADIENT = "gradient"
    INVERT = "invert"
    MIN_GRADIENT = "min_gradient"
    SAMPLE_COUNT = "sample_count"
    SAMPLE_DURATION = "sample_duration"
