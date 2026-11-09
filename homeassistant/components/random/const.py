"""Constants for random helper."""

from enum import StrEnum

DOMAIN = "random"

DEFAULT_MIN = 0
DEFAULT_MAX = 20


class RandomEntityStateAttribute(StrEnum):
    """State attributes for random sensor entities."""

    MAXIMUM = "maximum"
    MINIMUM = "minimum"
