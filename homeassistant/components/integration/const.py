"""Constants."""
from homeassistant.const import TIME_DAYS, TIME_HOURS, TIME_MINUTES, TIME_SECONDS

DOMAIN = "integration"

CONF_SOURCE_SENSOR = "source"
CONF_ROUND_DIGITS = "round"
CONF_UNIT_PREFIX = "unit_prefix"
CONF_UNIT_TIME = "unit_time"
CONF_UNIT_OF_MEASUREMENT = "unit"

TRAPEZOIDAL_METHOD = "trapezoidal"
LEFT_METHOD = "left"
RIGHT_METHOD = "right"
INTEGRATION_METHOD = [TRAPEZOIDAL_METHOD, LEFT_METHOD, RIGHT_METHOD]

# SI Metric prefixes
UNIT_PREFIXES = {None: 1, "k": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}

# SI Time prefixes
UNIT_TIME = {
    TIME_SECONDS: 1,
    TIME_MINUTES: 60,
    TIME_HOURS: 60 * 60,
    TIME_DAYS: 24 * 60 * 60,
}

DEFAULT_ROUND = 3

ATTR_SOURCE_ID = "source"
