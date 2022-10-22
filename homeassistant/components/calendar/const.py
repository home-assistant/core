"""Constants for calendar components."""

from enum import IntEnum

CONF_EVENT = "event"


class CalendarEntityFeature(IntEnum):
    """Supported features of the calendar entity."""

    CREATE_EVENT = 1
    DELETE_EVENT = 2


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
