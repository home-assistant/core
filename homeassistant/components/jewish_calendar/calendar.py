"""Jewish Calendar calendar platform."""

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

from .const import CONF_CALENDAR_EVENTS, DEFAULT_CALENDAR_EVENTS
from .entity import JewishCalendarConfigEntry, JewishCalendarEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

CALENDARS = (
    CalendarEntityDescription(key="events", name="Events", icon="mdi:calendar"),
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

    def __init__(
        self,
        config_entry: JewishCalendarConfigEntry,
        description: CalendarEntityDescription,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(config_entry, description)
        self._events_config = config_entry.options.get(
            CONF_CALENDAR_EVENTS, DEFAULT_CALENDAR_EVENTS
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

        info = HDateInfo(target_date, self.data.diaspora)
        zmanim = self.make_zmanim(target_date)

        for event_type in self._events_config:
            if _events := self._create_event_for_type(
                event_type, target_date, info, zmanim
            ):
                events.extend(_events if isinstance(_events, list) else [_events])

        return events

    def _create_event_for_type(
        self, event_type: str, target_date: date, info: HDateInfo, zmanim: Zmanim
    ) -> list[CalendarEvent] | CalendarEvent | None:
        """Create a calendar event for the specified type."""
        if event_type == "date":
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"{info.hdate}",
                description=f"Hebrew date: {info.hdate}",
            )

        if event_type == "holiday" and info.holidays:
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

        if event_type == "weekly_portion" and info.parasha:
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"{info.parasha}",
                description=f"Parshat Hashavua: {info.parasha}",
            )

        if event_type == "omer_count" and info.omer.total_days > 0:
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"{info.omer}",
                description=f"Sefirat HaOmer: {info.omer.count_str()}",
            )

        if event_type == "daf_yomi" and info.daf_yomi:
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"{info.daf_yomi}",
                description=f"Daf Yomi: {info.daf_yomi}",
            )

        if event_type == "candle_lighting" and zmanim.candle_lighting:
            return CalendarEvent(
                start=zmanim.candle_lighting.astimezone(UTC),
                end=zmanim.candle_lighting.astimezone(UTC),
                summary="Candle Lighting",
                description=f"Candle lighting time: {zmanim.candle_lighting.strftime('%H:%M')}",
            )

        if event_type == "havdalah" and zmanim.havdalah:
            return CalendarEvent(
                start=zmanim.havdalah.astimezone(UTC),
                end=zmanim.havdalah.astimezone(UTC),
                summary="Havdalah",
                description=f"Havdalah time: {zmanim.havdalah.strftime('%H:%M')}",
            )

        return None

    def _update_times(self, zmanim: Zmanim) -> list[datetime | None]:
        """Return a list of times to update the calendar."""
        # Update at midnight to refresh daily events
        return [None]
