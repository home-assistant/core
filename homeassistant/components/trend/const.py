"""Constant values for Trend integration."""

DOMAIN = "trend"

ATTR_ATTRIBUTE = "attribute"
ATTR_GRADIENT = "gradient"
ATTR_INVERT = "invert"
ATTR_MIN_GRADIENT = "min_gradient"
ATTR_SAMPLE_DURATION = "sample_duration"
ATTR_SAMPLE_COUNT = "sample_count"

CONF_INVERT = "invert"
CONF_MAX_SAMPLES = "max_samples"
CONF_MIN_GRADIENT = "min_gradient"
CONF_MIN_GRADIENT_VALUE = "min_gradient_value"
CONF_MIN_GRADIENT_TIME_UNIT = "min_gradient_time_unit"
CONF_SAMPLE_DURATION = "sample_duration"
CONF_MIN_SAMPLES = "min_samples"

DEFAULT_MAX_SAMPLES = 2
DEFAULT_MIN_SAMPLES = 2
DEFAULT_MIN_GRADIENT = 0.0
DEFAULT_MIN_GRADIENT_VALUE = 0.0
DEFAULT_MIN_GRADIENT_TIME_UNIT = "hour"
DEFAULT_SAMPLE_DURATION = 0

# Time unit conversion factors (to seconds)
TIME_UNIT_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}
