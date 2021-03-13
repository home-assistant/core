"""Constants for buienradar component."""

DOMAIN = "buienradar"

DEFAULT_TIMEFRAME = 60

DEFAULT_DIMENSION = 700
DEFAULT_DELTA = 600

HOME_LOCATION_NAME = "Home"

CONF_CAMERA = "camera"
CONF_SENSOR = "sensor"
CONF_WEATHER = "weather"
CONF_DIMENSION = "dimension"
CONF_DELTA = "delta"
CONF_COUNTRY = "country_code"
CONF_TIMEFRAME = "timeframe"

"""Range according to the docs"""
CAMERA_DIM_MIN = 120
CAMERA_DIM_MAX = 700

SUPPORTED_COUNTRY_CODES = ["NL", "BE"]
DEFAULT_COUNTRY = "NL"

"""Schedule next call after (minutes)."""
SCHEDULE_OK = 10
"""When an error occurred, new call after (minutes)."""
SCHEDULE_NOK = 2
