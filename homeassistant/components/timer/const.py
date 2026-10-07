"""Constants for the timer integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import TimerData

DOMAIN: Final = "timer"

DATA_TIMER: HassKey[TimerData] = HassKey(DOMAIN)

DEFAULT_DURATION: Final = 0

ATTR_DURATION: Final = "duration"

SERVICE_START: Final = "start"
SERVICE_PAUSE: Final = "pause"
SERVICE_CANCEL: Final = "cancel"
SERVICE_CHANGE: Final = "change"
SERVICE_FINISH: Final = "finish"


class TimerEntityStateAttribute(StrEnum):
    """State attributes for timer entities."""

    DURATION = "duration"
    EDITABLE = "editable"
    LAST_TRANSITION = "last_transition"
    FINISHES_AT = "finishes_at"
    REMAINING = "remaining"
    RESTORE = "restore"
