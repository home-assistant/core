"""Provides the constants needed for the component."""

from enum import StrEnum

DOMAIN = "text"


class TextEntityCapabilityAttribute(StrEnum):
    """Capability attributes for text entities."""

    MODE = "mode"
    MIN = "min"
    MAX = "max"
    PATTERN = "pattern"


ATTR_MAX = "max"
ATTR_MIN = "min"
ATTR_PATTERN = "pattern"
ATTR_VALUE = "value"

SERVICE_SET_VALUE = "set_value"
