"""Constants for the Threshold integration."""

from enum import StrEnum
from typing import Final

DOMAIN: Final = "threshold"

DEFAULT_HYSTERESIS: Final = 0.0

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


class ThresholdEntityStateAttribute(StrEnum):
    """State attributes for threshold entities."""

    ENTITY_ID = "entity_id"
    HYSTERESIS = "hysteresis"
    LOWER = "lower"
    POSITION = "position"
    SENSOR_VALUE = "sensor_value"
    TYPE = "type"
    UPPER = "upper"
