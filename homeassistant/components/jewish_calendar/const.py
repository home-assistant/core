"""Jewish Calendar constants."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Self

DOMAIN = "jewish_calendar"

ATTR_AFTER_SUNSET = "after_sunset"
ATTR_DATE = "date"
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
    """Daily Calendar event types with metadata."""

    DATE = "date"
    ALOT_HASHACHAR = (
        "alot_hashachar",
        "Alot Hashachar",  # codespell:ignore alot
        "Halachic dawn",
    )
    NETZ_HACHAMA = ("netz_hachama", "Netz Hachama", "Halachic sunrise")
    SOF_ZMAN_SHEMA_GRA = (
        "sof_zman_shema_gra",
        'Sof Zman Shema (Gr"A)',  # codespell:ignore shema
        "Latest time for Shema",  # codespell:ignore shema
    )
    SOF_ZMAN_SHEMA_MGA = (
        "sof_zman_shema_mga",
        'Sof Zman Shema (Mg"A)',  # codespell:ignore shema
        "Latest time for Shema",  # codespell:ignore shema
    )
    SOF_ZMAN_TFILLA_GRA = (
        "sof_zman_tfilla_gra",
        'Sof Zman Tefilla (Gr"A)',
        "Latest time for Tefilla",
    )
    SOF_ZMAN_TFILLA_MGA = (
        "sof_zman_tfilla_mga",
        'Sof Zman Tefilla (Mg"A)',
        "Latest time for Tefilla",
    )
    CHATZOT_HAYOM = ("chatzot_hayom", "Chatzot Hayom", "Halachic midday")
    MINCHA_GEDOLA = ("mincha_gedola", "Mincha Gedola", "Earliest time for Mincha")
    MINCHA_KETANA = ("mincha_ketana", "Mincha Ketana", "Preferable time for Mincha")
    PLAG_HAMINCHA = ("plag_hamincha", "Plag Hamincha", "Plag Hamincha")
    SHKIA = ("shkia", "Shkia", "Sunset")
    TSET_HAKOHAVIM = ("tset_hakohavim_tsom", "T'set Hakochavim", "Nightfall")

    if TYPE_CHECKING:
        _summary: str
        _description_prefix: str

    def __new__(
        cls, value: str, summary: str = "", description_prefix: str = ""
    ) -> Self:
        """Create new enum member with additional attributes."""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._summary = summary  # noqa: SLF001
        obj._description_prefix = description_prefix  # noqa: SLF001
        return obj

    @property
    def summary(self) -> str:
        """Return the summary for the event."""
        return self._summary

    @property
    def description_prefix(self) -> str:
        """Return the description prefix for the event."""
        return self._description_prefix


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
        DailyCalendarEventType.ALOT_HASHACHAR,
        DailyCalendarEventType.NETZ_HACHAMA,
        DailyCalendarEventType.SOF_ZMAN_SHEMA_GRA,
        DailyCalendarEventType.SOF_ZMAN_TFILLA_GRA,
        DailyCalendarEventType.CHATZOT_HAYOM,
        DailyCalendarEventType.MINCHA_GEDOLA,
        DailyCalendarEventType.MINCHA_KETANA,
        DailyCalendarEventType.PLAG_HAMINCHA,
        DailyCalendarEventType.SHKIA,
        DailyCalendarEventType.TSET_HAKOHAVIM,
    ],
    CONF_LEARNING_SCHEDULE: [LearningScheduleEventType.DAF_YOMI],
    CONF_YEARLY_EVENTS: [
        YearlyCalendarEventType.HOLIDAY,
        YearlyCalendarEventType.WEEKLY_PORTION,
        YearlyCalendarEventType.OMER_COUNT,
    ],
}


SERVICE_COUNT_OMER = "count_omer"
