"""Jewish Calendar constants."""

from enum import StrEnum, auto

DOMAIN = "jewish_calendar"

ATTR_AFTER_SUNSET = "after_sunset"
ATTR_DATE = "date"
ATTR_NUSACH = "nusach"

CONF_ALTITUDE = "altitude"  # The name used by the hdate library for elevation
CONF_DIASPORA = "diaspora"
CONF_CANDLE_LIGHT_MINUTES = "candle_lighting_minutes_before_sunset"
CONF_HAVDALAH_OFFSET_MINUTES = "havdalah_minutes_after_sunset"
CONF_CALENDAR_EVENTS = "calendar_events"

DEFAULT_NAME = "Jewish Calendar"
DEFAULT_CANDLE_LIGHT = 18
DEFAULT_DIASPORA = False
DEFAULT_HAVDALAH_OFFSET_MINUTES = 0
DEFAULT_LANGUAGE = "en"


class CalendarEventType(StrEnum):
    """Calendar event types."""

    DATE = auto()
    HOLIDAY = auto()
    WEEKLY_PORTION = auto()
    OMER_COUNT = auto()
    DAF_YOMI = auto()
    CANDLE_LIGHTING = auto()
    HAVDALAH = auto()


DEFAULT_CALENDAR_EVENTS = [
    CalendarEventType.DATE,
    CalendarEventType.HOLIDAY,
    CalendarEventType.WEEKLY_PORTION,
    CalendarEventType.OMER_COUNT,
    CalendarEventType.DAF_YOMI,
]

SERVICE_COUNT_OMER = "count_omer"
