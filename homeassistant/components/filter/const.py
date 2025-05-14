"""The filter component constants."""

from homeassistant.const import Platform

DOMAIN = "filter"
PLATFORMS = [Platform.SENSOR]

CONF_INDEX = "index"

FILTER_NAME_RANGE = "range"
FILTER_NAME_LOWPASS = "lowpass"
FILTER_NAME_OUTLIER = "outlier"
FILTER_NAME_THROTTLE = "throttle"
FILTER_NAME_TIME_THROTTLE = "time_throttle"
FILTER_NAME_TIME_SMA = "time_simple_moving_average"

CONF_FILTERS = "filters"
CONF_FILTER_NAME = "filter"
CONF_FILTER_WINDOW_SIZE = "window_size"
CONF_FILTER_PRECISION = "precision"
CONF_FILTER_RADIUS = "radius"
CONF_FILTER_TIME_CONSTANT = "time_constant"
CONF_FILTER_LOWER_BOUND = "lower_bound"
CONF_FILTER_UPPER_BOUND = "upper_bound"
CONF_TIME_SMA_TYPE = "type"

TIME_SMA_LAST = "last"

WINDOW_SIZE_UNIT_NUMBER_EVENTS = 1
WINDOW_SIZE_UNIT_TIME = 2

DEFAULT_NAME = "Filtered sensor"
DEFAULT_WINDOW_SIZE = 1
DEFAULT_PRECISION = 2
DEFAULT_FILTER_RADIUS = 2.0
DEFAULT_FILTER_TIME_CONSTANT = 10
