"""Jewish Calendar calendar platform."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import logging

from hdate import HDateInfo, Zmanim

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DAILY_EVENTS,
    CONF_LEARNING_SCHEDULE,
    CONF_YEARLY_EVENTS,
    DEFAULT_CALENDAR_EVENTS,
    DailyCalendarEventType,
    LearningScheduleEventType,
    YearlyCalendarEventType,
)
from .entity import JewishCalendarConfigEntry, JewishCalendarEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


type JewishCalendarEventType = (
    DailyCalendarEventType | LearningScheduleEventType | YearlyCalendarEventType
)


@dataclass(frozen=True, kw_only=True)
class JewishCalendarCalendarEntityDescription(CalendarEntityDescription):
    """Jewish Calendar calendar entity description."""

    set_value_fn: Callable[
        [JewishCalendarEventType, date, HDateInfo, Zmanim],
        list[CalendarEvent] | CalendarEvent | None,
    ]


def _create_daily_event(
    event_type: JewishCalendarEventType,
    target_date: date,
    info: HDateInfo,
    zmanim: Zmanim,
) -> CalendarEvent | None:
    """Create a daily calendar event."""
    # Hebrew date
    if event_type == DailyCalendarEventType.DATE:
        return CalendarEvent(
            start=target_date,
            end=target_date,
            summary=f"{info.hdate}",
            description=f"Hebrew date: {info.hdate}",
        )

    # Time-based daily events using enum properties
    daily_event = DailyCalendarEventType(event_type)
    time_value = zmanim.zmanim.get(daily_event.value)

    if time_value is not None:
        return CalendarEvent(
            start=time_value.utc,
            end=time_value.utc,
            summary=daily_event.summary,
            description=f"{daily_event.description_prefix}: {time_value.local.strftime('%H:%M')}",
        )

    return None  # Should never happen


def _create_yearly_event(
    event_type: JewishCalendarEventType,
    target_date: date,
    info: HDateInfo,
    zmanim: Zmanim,
) -> list[CalendarEvent] | CalendarEvent | None:
    """Create a yearly calendar event."""
    # Holidays
    if event_type == YearlyCalendarEventType.HOLIDAY and info.holidays:
        return [
            CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"{holiday}",
                description=(
                    f"Jewish Holiday: {holiday}\nHoliday Type: {holiday.type}"
                ),
            )
            for holiday in info.holidays
        ]

    # Weekly portion
    if event_type == YearlyCalendarEventType.WEEKLY_PORTION and info.parasha:
        return CalendarEvent(
            start=target_date,
            end=target_date,
            summary=f"{info.parasha}",
            description=f"Parshat Hashavua: {info.parasha}",
        )

    # Omer count
    if event_type == YearlyCalendarEventType.OMER_COUNT and info.omer.total_days > 0:
        return CalendarEvent(
            start=target_date,
            end=target_date,
            summary=str(info.omer),
            description=f"Sefirat HaOmer: {info.omer.count_str()}",
        )

    # Candle lighting
    if event_type == YearlyCalendarEventType.CANDLE_LIGHTING and zmanim.candle_lighting:
        return CalendarEvent(
            start=zmanim.candle_lighting.astimezone(UTC),
            end=zmanim.candle_lighting.astimezone(UTC),
            summary="Candle Lighting",
            description=f"Candle lighting time: {zmanim.candle_lighting.strftime('%H:%M')}",
        )

    # Havdalah
    if event_type == YearlyCalendarEventType.HAVDALAH and zmanim.havdalah:
        return CalendarEvent(
            start=zmanim.havdalah.astimezone(UTC),
            end=zmanim.havdalah.astimezone(UTC),
            summary="Havdalah",
            description=f"Havdalah time: {zmanim.havdalah.strftime('%H:%M')}",
        )

    return None


def _create_learning_event(
    event_type: JewishCalendarEventType,
    target_date: date,
    info: HDateInfo,
    zmanim: Zmanim,
) -> CalendarEvent | None:
    """Create a learning schedule event."""
    # Daf Yomi
    if event_type == LearningScheduleEventType.DAF_YOMI and info.daf_yomi:
        return CalendarEvent(
            start=target_date,
            end=target_date,
            summary=f"{info.daf_yomi}",
            description=f"Daf Yomi: {info.daf_yomi}",
        )

    return None


CALENDARS = (
    JewishCalendarCalendarEntityDescription(
        key=CONF_DAILY_EVENTS,
        translation_key=CONF_DAILY_EVENTS,
        set_value_fn=_create_daily_event,
    ),
    JewishCalendarCalendarEntityDescription(
        key=CONF_LEARNING_SCHEDULE,
        translation_key=CONF_LEARNING_SCHEDULE,
        set_value_fn=_create_learning_event,
    ),
    JewishCalendarCalendarEntityDescription(
        key=CONF_YEARLY_EVENTS,
        translation_key=CONF_YEARLY_EVENTS,
        set_value_fn=_create_yearly_event,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JewishCalendarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Jewish Calendar config entry."""
    async_add_entities(
        JewishCalendar(config_entry, description) for description in CALENDARS
    )


class JewishCalendar(JewishCalendarEntity, CalendarEntity):
    """Representation of a Jewish Calendar element."""

    entity_description: JewishCalendarCalendarEntityDescription

    def __init__(
        self,
        config_entry: JewishCalendarConfigEntry,
        description: JewishCalendarCalendarEntityDescription,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(config_entry, description)
        self._events_config = config_entry.options.get(
            description.key, DEFAULT_CALENDAR_EVENTS[description.key]
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        # Get today's events first
        today = datetime.now().date()
        events = self._get_events_for_date(today)

        if events:
            # Return the first event of today
            return events[0]

        # Look for the next event in the next 30 days
        for days_ahead in range(1, 31):
            future_date = today + timedelta(days=days_ahead)
            events = self._get_events_for_date(future_date)
            if events:
                return events[0]

        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events = []

        # Convert datetime to date for iteration
        start_ordinal = start_date.date().toordinal()
        end_ordinal = end_date.date().toordinal()

        for ordinal in range(start_ordinal, end_ordinal + 1):
            current_date = date.fromordinal(ordinal)
            day_events = self._get_events_for_date(current_date)
            events.extend(day_events)

        return events

    def _get_events_for_date(self, target_date: date) -> list[CalendarEvent]:
        """Get all configured events for a specific date."""
        events = []

        info = HDateInfo(target_date, self.coordinator.data.diaspora)
        zmanim = self.coordinator.make_zmanim(target_date)

        for event_type in self._events_config:
            if _events := self.entity_description.set_value_fn(
                event_type, target_date, info, zmanim
            ):
                events.extend(_events if isinstance(_events, list) else [_events])

        return events

    def _update_times(self, zmanim: Zmanim) -> list[datetime | None]:
        """Return a list of times to update the calendar."""
        # Calendar entities do not require periodic updates besides the retrieval of events.
        return [None]
