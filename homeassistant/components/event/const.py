"""Provides the constants needed for the component."""

from enum import StrEnum
from functools import partial
from typing import Final

from homeassistant.helpers.deprecation import (
    DeprecatedConstant,
    EnumWithDeprecatedMembers,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

DOMAIN: Final = "event"

ATTR_EVENT_TYPE = "event_type"
ATTR_EVENT_TYPES = "event_types"
ATTR_PRESS_COUNT = "press_count"
_DEPRECATED_ATTR_MULTI_PRESS_COUNT = DeprecatedConstant(
    "multi_press_count", "ATTR_PRESS_COUNT", "2027.5.0"
)


class EventEntityCapabilityAttribute(StrEnum):
    """Capability attributes for event entities."""

    EVENT_TYPES = "event_types"


class EventEntityStateAttribute(StrEnum):
    """State attributes for event entities."""

    EVENT_TYPE = "event_type"


class DoorbellEventType(StrEnum):
    """Standard event types for doorbell device class."""

    RING = "ring"


class ButtonEventType(
    StrEnum,
    metaclass=EnumWithDeprecatedMembers,
    deprecated={
        "MULTI_PRESS_ONGOING": ("an integration specific event type", "2027.5.0"),
        "MULTI_PRESS_END": ("ButtonEventType.MULTI_PRESS", "2027.5.0"),
    },
):
    """Standard event types for button device class.

    None of these are mandatory: integrations map only the
    interactions their hardware can actually produce.
    """

    PRESS_START = "press_start"
    PRESS_END = "press_end"
    LONG_PRESS_START = "long_press_start"
    LONG_PRESS_END = "long_press_end"
    SINGLE_PRESS = "single_press"
    MULTI_PRESS = "multi_press"
    MULTI_PRESS_ONGOING = "multi_press_ongoing"  # Deprecated
    MULTI_PRESS_END = "multi_press_end"  # Deprecated


class EventDeviceClass(StrEnum):
    """Device class for events."""

    DOORBELL = "doorbell"
    BUTTON = "button"
    MOTION = "motion"


# These can be removed if no deprecated constants are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
