"""Constants for the counter integration."""

from enum import StrEnum


class CounterEntityStateAttribute(StrEnum):
    """State attributes for counter entities."""

    EDITABLE = "editable"
    INITIAL = "initial"
    STEP = "step"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
