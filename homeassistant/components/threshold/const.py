"""Constants for the Threshold integration."""

DOMAIN = "threshold"

CONF_HYSTERESIS = "hysteresis"
CONF_LOWER = "lower"
CONF_MODE = "mode"
CONF_UPPER = "upper"

TYPE_LOWER = "lower"
TYPE_RANGE = "range"
TYPE_UPPER = "upper"

THRESHOLD_MODES = [TYPE_LOWER, TYPE_UPPER, TYPE_RANGE]

DEFAULT_HYSTERESIS = 0.0
