"""Constants for the lock entity platform."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import LockEntity

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


DATA_COMPONENT: HassKey[EntityComponent[LockEntity]] = HassKey(DOMAIN)
