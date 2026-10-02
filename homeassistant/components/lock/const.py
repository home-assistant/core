"""Constants for the lock entity platform."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import LockEntity

DOMAIN: Final = "lock"
DATA_COMPONENT: HassKey[EntityComponent[LockEntity]] = HassKey(DOMAIN)


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


class LockEntityFeature(IntFlag):
    """Supported features of the lock entity."""

    OPEN = 1
