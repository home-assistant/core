"""Models for the Logger integration."""

from homeassistant.backports.enum import StrEnum


class LogPersistance(StrEnum):
    """Log persistence."""

    NONE = "none"
    ONCE = "once"
    PERMANENT = "permanent"
