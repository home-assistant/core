"""Constants for the Integration integration."""
from __future__ import annotations

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
UNIT_PREFIXES: dict[str | None, int] = {
    "k": 10**3,
    "M": 10**6,
    "G": 10**9,
    "T": 10**12,
}
PLATFORM_UNIT_PREFIXES: dict[str | None, int] = {None: 1, **UNIT_PREFIXES}

# SI Time prefixes
UNIT_TIME = {
    TIME_SECONDS: 1,
    TIME_MINUTES: 60,
    TIME_HOURS: 60 * 60,
    TIME_DAYS: 24 * 60 * 60,
}

DEFAULT_ROUND = 3
