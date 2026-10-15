"""Constants for the timer integration."""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import TimerData

DOMAIN: Final = "timer"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

DATA_TIMER: HassKey[TimerData] = HassKey(DOMAIN)

DEFAULT_DURATION: Final = 0
DEFAULT_RESTORE = False

ATTR_DURATION: Final = "duration"
ATTR_FINISHED_AT = "finished_at"

CONF_DURATION = "duration"
CONF_RESTORE = "restore"

STATUS_IDLE = "idle"
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"

EVENT_TIMER_FINISHED = "timer.finished"
EVENT_TIMER_CANCELLED = "timer.cancelled"
EVENT_TIMER_CHANGED = "timer.changed"
EVENT_TIMER_STARTED = "timer.started"
EVENT_TIMER_RESTARTED = "timer.restarted"
EVENT_TIMER_PAUSED = "timer.paused"

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
