"""Jewish Calendar calendar platform."""

from datetime import UTC, date, datetime, timedelta
import logging

from hdate import HDateInfo, HolidayTypes, Zmanim

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CALENDAR_EVENTS, DEFAULT_CALENDAR_EVENTS
from .entity import JewishCalendarConfigEntry, JewishCalendarEntity

_LOGGER = logging.getLogger(__name__)
CALENDAR_TYPES: tuple[EntityDescription, ...] = (
    EntityDescription(
        key="events",
        name="Events",
        icon="mdi:calendar",
        entity_registry_enabled_default=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JewishCalendarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Jewish Calendar config entry."""
    async_add_entities(
        JewishCalendar(config_entry, description) for description in CALENDAR_TYPES
    )


class JewishCalendar(JewishCalendarEntity, CalendarEntity):
    """Representation of a Jewish Calendar element."""

    def __init__(
        self,
        config_entry: JewishCalendarConfigEntry,
        description: EntityDescription,
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
            event = self._create_event_for_type(event_type, target_date, info, zmanim)
            if event:
                events.append(event)

        return events

    def _create_event_for_type(
        self, event_type: str, target_date: date, info: HDateInfo, zmanim: Zmanim
    ) -> CalendarEvent | None:
        """Create a calendar event for the specified type."""
        if event_type == "date":
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=str(info.hdate),
                description=f"Hebrew date: {info.hdate}",
            )

        if event_type == "holiday" and info.holidays:
            holiday_names = ", ".join(str(holiday) for holiday in info.holidays)
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=holiday_names,
                description=f"Jewish Holiday: {holiday_names}",
            )

        if event_type == "weekly_portion" and info.upcoming_shabbat.parasha:
            # Only show on the Shabbat itself or Friday
            if (
                target_date.weekday() == 4 or target_date.weekday() == 5
            ):  # Friday or Saturday
                return CalendarEvent(
                    start=target_date,
                    end=target_date,
                    summary=f"Torah Portion: {info.upcoming_shabbat.parasha}",
                    description=f"Weekly Torah portion: {info.upcoming_shabbat.parasha}",
                )

        elif event_type == "omer_count" and info.omer.total_days > 0:
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"Omer Day {info.omer.total_days}",
                description=f"Day {info.omer.total_days} of the Omer count",
            )

        elif event_type == "daf_yomi" and info.daf_yomi:
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"Daf Yomi: {info.daf_yomi}",
                description=f"Daily Talmud study: {info.daf_yomi}",
            )

        elif event_type == "candle_lighting" and zmanim.candle_lighting:
            # Only show on Friday and Holiday eves
            if target_date.weekday() == 4 or self._is_erev_yom_tov(info):
                return CalendarEvent(
                    start=zmanim.candle_lighting.astimezone(UTC),
                    end=zmanim.candle_lighting.astimezone(UTC),
                    summary="Candle Lighting",
                    description=f"Candle lighting time: {zmanim.candle_lighting.strftime('%H:%M')}",
                )

        elif event_type == "havdalah" and zmanim.havdalah:
            # Only show on Saturday and Holiday ends
            if target_date.weekday() == 5 or self._is_yom_tov(info):
                return CalendarEvent(
                    start=zmanim.havdalah.astimezone(UTC),
                    end=zmanim.havdalah.astimezone(UTC),
                    summary="Havdalah",
                    description=f"Havdalah time: {zmanim.havdalah.strftime('%H:%M')}",
                )

        elif event_type == "fast_day" and self._is_fast_day(info):
            fast_name = self._get_holiday_name(info)
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"Fast Day: {fast_name}",
                description=f"Jewish fast day: {fast_name}",
            )

        elif event_type == "rosh_chodesh" and self._is_rosh_chodesh(info):
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary="Rosh Chodesh",
                description="Beginning of the Hebrew month",
            )

        elif event_type == "minor_fast" and self._is_minor_fast(info):
            fast_name = self._get_holiday_name(info)
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"Minor Fast: {fast_name}",
                description=f"Jewish minor fast day: {fast_name}",
            )

        elif event_type == "modern_holiday" and self._is_modern_holiday(info):
            holiday_name = self._get_holiday_name(info)
            return CalendarEvent(
                start=target_date,
                end=target_date,
                summary=f"Modern Holiday: {holiday_name}",
                description=f"Modern Jewish holiday: {holiday_name}",
            )

        return None

    def _is_erev_yom_tov(self, info: HDateInfo) -> bool:
        """Check if today is erev yom tov (eve of major holiday)."""
        return any(
            holiday.type == HolidayTypes.EREV_YOM_TOV for holiday in info.holidays
        )

    def _is_yom_tov(self, info: HDateInfo) -> bool:
        """Check if today is yom tov (major holiday)."""
        return any(holiday.type == HolidayTypes.YOM_TOV for holiday in info.holidays)

    def _is_fast_day(self, info: HDateInfo) -> bool:
        """Check if today is a fast day."""
        return any(holiday.type == HolidayTypes.FAST_DAY for holiday in info.holidays)

    def _is_minor_fast(self, info: HDateInfo) -> bool:
        """Check if today is a minor fast day (subset of fast days)."""
        # Minor fasts are typically the four fasts (not Yom Kippur or Tisha B'Av)
        if not self._is_fast_day(info):
            return False

        # Check if it's a minor holiday type fast
        return any(
            holiday.type == HolidayTypes.MINOR_HOLIDAY
            and holiday.name
            in ["tzom_gedalia", "asara_btevet", "taanit_esther", "tzom_tammuz"]
            for holiday in info.holidays
        )

    def _is_rosh_chodesh(self, info: HDateInfo) -> bool:
        """Check if today is Rosh Chodesh."""
        return any(
            holiday.type == HolidayTypes.ROSH_CHODESH for holiday in info.holidays
        )

    def _is_modern_holiday(self, info: HDateInfo) -> bool:
        """Check if today is a modern Jewish holiday."""
        return any(
            holiday.type
            in (HolidayTypes.MODERN_HOLIDAY, HolidayTypes.ISRAEL_NATIONAL_HOLIDAY)
            for holiday in info.holidays
        )

    def _get_holiday_name(self, info: HDateInfo) -> str:
        """Get the name of the first holiday."""
        if info.holidays:
            return str(info.holidays[0])
        return "Holiday"

    def _update_times(self, zmanim: Zmanim) -> list[datetime | None]:
        """Return a list of times to update the calendar."""
        # Update at midnight to refresh daily events
        return [None]
