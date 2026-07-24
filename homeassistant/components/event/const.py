"""Provides the constants needed for the component."""

from enum import StrEnum

DOMAIN = "event"
ATTR_EVENT_TYPE = "event_type"
ATTR_EVENT_TYPES = "event_types"
ATTR_MULTI_PRESS_COUNT = "multi_press_count"


class EventEntityCapabilityAttribute(StrEnum):
    """Capability attributes for event entities."""

    EVENT_TYPES = "event_types"


class EventEntityStateAttribute(StrEnum):
    """State attributes for event entities."""

    EVENT_TYPE = "event_type"


class DoorbellEventType(StrEnum):
    """Standard event types for doorbell device class."""

    RING = "ring"


class ButtonEventType(StrEnum):
    """Standard event types for button device class.

    None of these are mandatory: integrations map only the
    interactions their hardware can actually produce.
    """

    PRESS_START = "press_start"
    PRESS_END = "press_end"
    LONG_PRESS_START = "long_press_start"
    LONG_PRESS_END = "long_press_end"
    MULTI_PRESS_ONGOING = "multi_press_ongoing"
    MULTI_PRESS_END = "multi_press_end"
