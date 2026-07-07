"""Constants for the timer integration."""

from enum import StrEnum


class TimerEntityStateAttribute(StrEnum):
    """State attributes for timer entities."""

    DURATION = "duration"
    EDITABLE = "editable"
    LAST_TRANSITION = "last_transition"
    FINISHES_AT = "finishes_at"
    REMAINING = "remaining"
    RESTORE = "restore"
