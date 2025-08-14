"""Jewish Calendar constants."""

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
DEFAULT_CALENDAR_EVENTS = [
    "date",
    "holiday",
    "weekly_portion",
    "omer_count",
    "daf_yomi",
]

SERVICE_COUNT_OMER = "count_omer"

# Available calendar event types
CALENDAR_EVENT_TYPES = [*DEFAULT_CALENDAR_EVENTS, "candle_lighting", "havdalah"]
