"""Provides the constants needed for the component."""

from enum import StrEnum

DOMAIN = "event"
ATTR_EVENT_TYPE = "event_type"
ATTR_EVENT_TYPES = "event_types"


class EventEntityCapabilityAttribute(StrEnum):
    """Capability attributes for event entities."""

    EVENT_TYPES = "event_types"


class EventEntityStateAttribute(StrEnum):
    """State attributes for event entities."""

    EVENT_TYPE = "event_type"


class DoorbellEventType(StrEnum):
    """Standard event types for doorbell device class."""

    RING = "ring"
