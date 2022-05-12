"""Constants for buienradar component."""

DOMAIN = "buienradar"

DEFAULT_TIMEFRAME = 60

DEFAULT_DIMENSION = 700
DEFAULT_DELTA = 600

CONF_DELTA = "delta"
CONF_COUNTRY = "country_code"
CONF_TIMEFRAME = "timeframe"

SUPPORTED_COUNTRY_CODES = ["NL", "BE"]
DEFAULT_COUNTRY = "NL"

"""Schedule next call after (minutes)."""
SCHEDULE_OK = 10
"""When an error occurred, new call after (minutes)."""
SCHEDULE_NOK = 2
