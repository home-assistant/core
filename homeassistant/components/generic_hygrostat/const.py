"""Constants for the Generic Hygrostat integration."""

from enum import StrEnum


class GenericHygrostatEntityStateAttribute(StrEnum):
    """State attributes for generic hygrostat entities."""

    SAVED_HUMIDITY = "saved_humidity"
