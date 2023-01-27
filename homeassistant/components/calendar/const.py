"""Constants for calendar components."""

from enum import IntEnum

CONF_EVENT = "event"


class CalendarEntityFeature(IntEnum):
    """Supported features of the calendar entity."""

    CREATE_EVENT = 1
    DELETE_EVENT = 2
    UPDATE_EVENT = 4


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
