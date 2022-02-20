"""Provides the constants needed for the component."""

from typing import Final

ATTR_VALUE = "value"
ATTR_MIN = "min"
ATTR_MAX = "max"
ATTR_STEP = "step"

DEFAULT_MIN_VALUE = 0.0
DEFAULT_MAX_VALUE = 100.0
DEFAULT_STEP = 1.0

DOMAIN = "number"

SERVICE_SET_VALUE = "set_value"

# MODE_* are deprecated as of 2021.12, use the NumberMode enum instead.
MODE_AUTO: Final = "auto"
MODE_BOX: Final = "box"
MODE_SLIDER: Final = "slider"
