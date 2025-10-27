"""Calendar platform for La Marzocco espresso machines."""

from collections.abc import Iterator
from datetime import datetime, timedelta

from pylamarzocco.const import WeekDay

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LaMarzoccoConfigEntry, LaMarzoccoUpdateCoordinator
from .entity import LaMarzoccoBaseEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

CALENDAR_KEY = "auto_on_off_schedule"

WEEKDAY_TO_ENUM = {
    0: WeekDay.MONDAY,
    1: WeekDay.TUESDAY,
    2: WeekDay.WEDNESDAY,
    3: WeekDay.THURSDAY,
    4: WeekDay.FRIDAY,
    5: WeekDay.SATURDAY,
    6: WeekDay.SUNDAY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities and services."""

    coordinator = entry.runtime_data.schedule_coordinator

    async_add_entities(
        LaMarzoccoCalendarEntity(coordinator, CALENDAR_KEY, schedule.identifier)
        for schedule in coordinator.device.schedule.smart_wake_up_sleep.schedules
        if schedule.identifier
    )


class LaMarzoccoCalendarEntity(LaMarzoccoBaseEntity, CalendarEntity):
    """Class representing a La Marzocco calendar."""

    _attr_translation_key = CALENDAR_KEY

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        key: str,
        identifier: str,
    ) -> None:
        """Set up calendar."""
        super().__init__(coordinator, f"{key}_{identifier}")
        self._identifier = identifier
        self._attr_translation_placeholders = {"id": identifier}

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()

        events = self._get_events(
            start_date=now,
            end_date=now + timedelta(days=7),  # only need to check a week ahead
        )
        return next(iter(events), None)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        return self._get_events(
            start_date=start_date,
            end_date=end_date,
        )

    def _get_events(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Get calendar events within a datetime range."""

        events: list[CalendarEvent] = []
        for date in self._get_date_range(start_date, end_date):
            if scheduled := self._async_get_calendar_event(date):
                if scheduled.end < start_date:
                    continue
                if scheduled.start > end_date:
                    continue
                events.append(scheduled)
        return events

    def _get_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> Iterator[datetime]:
        current_date = start_date
        while current_date.date() < end_date.date():
            yield current_date
            current_date += timedelta(days=1)
        yield end_date

    def _async_get_calendar_event(self, date: datetime) -> CalendarEvent | None:
        """Return calendar event for a given weekday."""

        schedule_entry = (
            self.coordinator.device.schedule.smart_wake_up_sleep.schedules_dict[
                self._identifier
            ]
        )
        # check first if auto/on off is turned on in general
        if not schedule_entry.enabled:
            return None

        # parse the schedule for the day

        if WEEKDAY_TO_ENUM[date.weekday()] not in schedule_entry.days:
            return None

        hour_on = schedule_entry.on_time_minutes // 60
        minute_on = schedule_entry.on_time_minutes % 60
        hour_off = schedule_entry.off_time_minutes // 60
        minute_off = schedule_entry.off_time_minutes % 60

        day_offset = 0
        if hour_off == 24:
            # if the machine is scheduled to turn off at midnight, we need to
            # set the end date to the next day
            day_offset = 1
            hour_off = 0

        end_date = date.replace(
            hour=int(hour_off),
            minute=int(minute_off),
        )
        end_date += timedelta(days=day_offset)

        return CalendarEvent(
            start=date.replace(
                hour=int(hour_on),
                minute=int(minute_on),
            ),
            end=end_date,
            summary=f"Machine {self.coordinator.config_entry.title} on",
            description="Machine is scheduled to turn on at the start time and off at the end time",
        )
