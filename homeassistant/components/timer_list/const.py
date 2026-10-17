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
ATTR_CREATED_DURATION = "created_duration"
ATTR_TOTAL_DURATION = "total_duration"
ATTR_DELTA = "delta"
ATTR_FINISHES_AT = "finishes_at"
ATTR_CREATED_AT = "created_at"
ATTR_ENDED_AT = "ended_at"
ATTR_REMAINING = "remaining"
ATTR_STATUS = "status"
ATTR_TIMER = "timer"
ATTR_TIMERS = "timers"


class TimerListServices(StrEnum):
    """Services for the Timer list integration."""

    CREATE_TIMER = "create_timer"
    PAUSE_TIMER = "pause_timer"
    UNPAUSE_TIMER = "unpause_timer"
    CANCEL_TIMER = "cancel_timer"
    FINISH_TIMER = "finish_timer"
    ADD_TIME = "add_time"
    SUBTRACT_TIME = "subtract_time"
    REMOVE_TIMER = "remove_timer"
    GET_TIMERS = "get_timers"


class TimerStatus(StrEnum):
    """Status of a single timer in a timer list."""

    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class TimerListEventType(StrEnum):
    """Type of change pushed to timer list subscribers."""

    CREATED = "created"
    PAUSED = "paused"
    UNPAUSED = "unpaused"
    TIME_CHANGED = "time_changed"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    REMOVED = "removed"


class TimerListEntityFeature(IntFlag):
    """Supported features of a timer list entity."""

    CREATE_TIMER = 1
    PAUSE_TIMER = 2
    CANCEL_TIMER = 4
    ADD_TIME = 8
    REMOVE_TIMER = 16
    FINISH_TIMER = 32
