"""Constants for the input_datetime component."""

from enum import StrEnum


class InputDatetimeEntityCapabilityAttribute(StrEnum):
    """Capability attributes for input datetime entities."""

    HAS_DATE = "has_date"
    HAS_TIME = "has_time"


class InputDatetimeEntityStateAttribute(StrEnum):
    """State attributes for input datetime entities."""

    EDITABLE = "editable"
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"
    TIMESTAMP = "timestamp"
