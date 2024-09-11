"""Constants for the Threshold integration."""

from typing import Final

DOMAIN: Final = "threshold"

DEFAULT_HYSTERESIS: Final = 0.0

ATTR_HYSTERESIS: Final = "hysteresis"
ATTR_LOWER: Final = "lower"
ATTR_POSITION: Final = "position"
ATTR_SENSOR_VALUE: Final = "sensor_value"
ATTR_TYPE: Final = "type"
ATTR_UPPER: Final = "upper"

CONF_HYSTERESIS: Final = "hysteresis"
CONF_LOWER: Final = "lower"
CONF_UPPER: Final = "upper"

POSITION_ABOVE: Final = "above"
POSITION_BELOW: Final = "below"
POSITION_IN_RANGE: Final = "in_range"
POSITION_UNKNOWN: Final = "unknown"

TYPE_LOWER: Final = "lower"
TYPE_RANGE: Final = "range"
TYPE_UPPER: Final = "upper"
