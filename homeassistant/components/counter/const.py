"""Constants for the counter integration."""

from enum import StrEnum

DOMAIN = "counter"


class CounterEntityStateAttribute(StrEnum):
    """State attributes for counter entities."""

    EDITABLE = "editable"
    INITIAL = "initial"
    STEP = "step"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
