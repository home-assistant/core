"""Constants for the lock entity platform."""

from enum import StrEnum
from typing import Final

DOMAIN: Final = "lock"


class LockEntityStateAttribute(StrEnum):
    """State attributes for lock entities."""

    CHANGED_BY = "changed_by"
    CODE_FORMAT = "code_format"


class LockState(StrEnum):
    """State of lock entities."""

    JAMMED = "jammed"
    OPENING = "opening"
    LOCKING = "locking"
    OPEN = "open"
    UNLOCKING = "unlocking"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
