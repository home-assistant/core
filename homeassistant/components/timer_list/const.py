"""Constants for the Timer list integration."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import TimerListEntity

DOMAIN = "timer_list"
DATA_COMPONENT: HassKey[EntityComponent[TimerListEntity]] = HassKey(DOMAIN)

ATTR_TIMER_ID = "timer_id"
ATTR_DURATION = "duration"
ATTR_FINISH_ACTION = "finish_action"
ATTR_FINISHES_AT = "finishes_at"
ATTR_CREATED_AT = "created_at"
ATTR_FINISHED_AT = "finished_at"
ATTR_REMAINING = "remaining"
ATTR_STATUS = "status"
ATTR_TIMER = "timer"
ATTR_TIMERS = "timers"


class TimerListServices(StrEnum):
    """Services for the Timer list integration."""

    START_TIMER = "start_timer"
    PAUSE_TIMER = "pause_timer"
    UNPAUSE_TIMER = "unpause_timer"
    CANCEL_TIMER = "cancel_timer"
    CANCEL_ALL_TIMERS = "cancel_all_timers"
    ADD_TIME = "add_time"
    REMOVE_TIME = "remove_time"
    REMOVE_TIMER = "remove_timer"
    CLEAR_FINISHED_TIMERS = "clear_finished_timers"
    GET_TIMERS = "get_timers"


class TimerStatus(StrEnum):
    """Status of a single timer in a timer list."""

    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class TimerFinishAction(StrEnum):
    """What happens to a timer once it finishes."""

    REMOVE = "remove"
    ARCHIVE = "archive"
    RESTART = "restart"


class TimerListEventType(StrEnum):
    """Type of change pushed to timer list subscribers."""

    STARTED = "started"
    UPDATED = "updated"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    REMOVED = "removed"


class TimerListEntityFeature(IntFlag):
    """Supported features of a timer list entity."""

    START_TIMER = 1
    PAUSE_TIMER = 2
    CANCEL_TIMER = 4
    ADD_TIME = 8
