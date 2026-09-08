"""Constants for calendar components."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import CalendarEntity

DOMAIN: Final = "calendar"
DATA_COMPONENT: HassKey[EntityComponent[CalendarEntity]] = HassKey(DOMAIN)


class CalendarEntityStateAttribute(StrEnum):
    """State attributes for calendar entities."""

    MESSAGE = "message"
    ALL_DAY = "all_day"
    START_TIME = "start_time"
    END_TIME = "end_time"
    LOCATION = "location"
    DESCRIPTION = "description"


class CalendarEntityFeature(IntFlag):
    """Supported features of the calendar entity."""

    CREATE_EVENT = 1
    DELETE_EVENT = 2
    UPDATE_EVENT = 4


class CalendarEventStatus(StrEnum):
    """Status of a calendar event.

    A subset of the statuses defined by the rfc5545 STATUS property: a calendar
    entity does not return cancelled events, so that value is not represented
    here.

    An event without a status is not the same as a confirmed event: it means
    the calendar did not report one, either because the source does not
    support it or because the integration does not read it yet.
    """

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"


# rfc5545 fields
EVENT_UID = "uid"
EVENT_START = "dtstart"
EVENT_END = "dtend"
EVENT_SUMMARY = "summary"
EVENT_DESCRIPTION = "description"
EVENT_LOCATION = "location"
EVENT_RECURRENCE_ID = "recurrence_id"
EVENT_RECURRENCE_RANGE = "recurrence_range"
EVENT_RRULE = "rrule"
EVENT_STATUS = "status"

# Service call fields
EVENT_START_DATE = "start_date"
EVENT_END_DATE = "end_date"
EVENT_START_DATETIME = "start_date_time"
EVENT_END_DATETIME = "end_date_time"
EVENT_IN = "in"
EVENT_IN_DAYS = "days"
EVENT_IN_WEEKS = "weeks"
EVENT_TIME_FIELDS = {
    EVENT_START_DATE,
    EVENT_END_DATE,
    EVENT_START_DATETIME,
    EVENT_END_DATETIME,
    EVENT_IN,
}
EVENT_TYPES = "event_types"
EVENT_DURATION = "duration"

# Fields for the list events service
LIST_EVENT_FIELDS = {
    "start",
    "end",
    EVENT_SUMMARY,
    EVENT_DESCRIPTION,
    EVENT_LOCATION,
    EVENT_STATUS,
}
