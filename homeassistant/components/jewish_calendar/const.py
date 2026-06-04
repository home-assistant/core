"""Jewish Calendar constants."""

from enum import StrEnum

DOMAIN = "jewish_calendar"

ATTR_AFTER_SUNSET = "after_sunset"
ATTR_NUSACH = "nusach"

CONF_ALTITUDE = "altitude"  # The name used by the hdate library for elevation
CONF_DIASPORA = "diaspora"
CONF_CANDLE_LIGHT_MINUTES = "candle_lighting_minutes_before_sunset"
CONF_HAVDALAH_OFFSET_MINUTES = "havdalah_minutes_after_sunset"
CONF_DAILY_EVENTS = "daily_events"
CONF_YEARLY_EVENTS = "yearly_events"
CONF_LEARNING_SCHEDULE = "learning_schedule"

DEFAULT_NAME = "Jewish Calendar"
DEFAULT_CANDLE_LIGHT = 18
DEFAULT_DIASPORA = False
DEFAULT_HAVDALAH_OFFSET_MINUTES = 0
DEFAULT_LANGUAGE = "en"


class DailyCalendarEventType(StrEnum):
    """Daily Calendar event types.

    The summary and description for each event are translated at runtime using
    the ``common`` strings of the integration (see ``calendar.py``).
    """

    DATE = "date"
    ALOT_HASHACHAR = "alot_hashachar"  # codespell:ignore alot
    NETZ_HACHAMA = "netz_hachama"
    SOF_ZMAN_SHEMA_GRA = "sof_zman_shema_gra"  # codespell:ignore shema
    SOF_ZMAN_SHEMA_MGA = "sof_zman_shema_mga"  # codespell:ignore shema
    SOF_ZMAN_TFILLA_GRA = "sof_zman_tfilla_gra"
    SOF_ZMAN_TFILLA_MGA = "sof_zman_tfilla_mga"
    CHATZOT_HAYOM = "chatzot_hayom"
    MINCHA_GEDOLA = "mincha_gedola"
    MINCHA_KETANA = "mincha_ketana"
    PLAG_HAMINCHA = "plag_hamincha"
    SHKIA = "shkia"
    TSET_HAKOHAVIM = "tset_hakohavim_tsom"


class YearlyCalendarEventType(StrEnum):
    """Yearly Calendar event types."""

    HOLIDAY = "holiday"
    WEEKLY_PORTION = "weekly_portion"
    OMER_COUNT = "omer_count"
    CANDLE_LIGHTING = "candle_lighting"
    HAVDALAH = "havdalah"


class LearningScheduleEventType(StrEnum):
    """Learning Schedule event types."""

    DAF_YOMI = "daf_yomi"


DEFAULT_CALENDAR_EVENTS = {
    CONF_DAILY_EVENTS: [
        DailyCalendarEventType.DATE,
        DailyCalendarEventType.NETZ_HACHAMA,
        DailyCalendarEventType.SHKIA,
        DailyCalendarEventType.TSET_HAKOHAVIM,
    ],
    CONF_LEARNING_SCHEDULE: [LearningScheduleEventType.DAF_YOMI],
    CONF_YEARLY_EVENTS: [
        YearlyCalendarEventType.HOLIDAY,
        YearlyCalendarEventType.WEEKLY_PORTION,
        YearlyCalendarEventType.CANDLE_LIGHTING,
        YearlyCalendarEventType.HAVDALAH,
    ],
}


SERVICE_COUNT_OMER = "count_omer"
